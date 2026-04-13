
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.providers.base import BaseVideoProviderAdapter
from app.providers.common import (
    ProviderConfigError,
    extract_nested,
    first_non_empty,
    make_callback_event,
    map_status_to_state,
    mock_query_result,
    mock_submit_result,
    provider_mock_enabled,
    request_json,
    verify_hmac_signature,
)
from app.schemas.provider_common import (
    NormalizedCallbackEvent,
    NormalizedStatusResult,
    NormalizedSubmitResult,
)


class KlingAdapter(BaseVideoProviderAdapter):
    provider_name = "kling"

    def _headers(self) -> dict[str, str]:
        if settings.kling_api_token:
            token = settings.kling_api_token
        else:
            raise ProviderConfigError(
                "KLING_API_TOKEN is required for direct Kling calls in this bundle. "
                "The official docs show AccessKey+SecretKey -> API Token generation, "
                "but the exact token algorithm was not fully visible in the provided source context."
            )
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _submit_body(self, scene_payload: dict[str, Any], callback_url: str | None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model_name": scene_payload.get("provider_model") or settings.kling_default_model,
            "prompt": scene_payload.get("prompt_text") or "",
            "mode": "std",
            "aspect_ratio": scene_payload.get("aspect_ratio") or "16:9",
            "duration": str(scene_payload.get("duration_seconds") or 5),
        }
        if callback_url:
            body["callback_url"] = callback_url
        seed = scene_payload.get("seed")
        if seed is not None:
            body["seed"] = int(seed)
        image = scene_payload.get("prompt_image_url")
        if image:
            body["image"] = image
        return body

    async def submit(self, scene_payload: dict, callback_url: str | None) -> NormalizedSubmitResult:
        model = scene_payload.get("provider_model") or settings.kling_default_model
        if provider_mock_enabled() and not settings.kling_api_token:
            return mock_submit_result(
                provider=self.provider_name,
                model=str(model),
                callback_url=callback_url,
                reason="KLING_API_TOKEN missing; using mock fallback",
            )

        data = await request_json(
            method="POST",
            url=f"{settings.kling_api_base_url.rstrip('/')}{settings.kling_text_to_video_path}",
            headers=self._headers(),
            json_body=self._submit_body(scene_payload, callback_url),
        )
        task_id = str(first_non_empty(data.get("request_id"), data.get("task_id"), extract_nested(data, "data", "task_id"), extract_nested(data, "data", "id")) or "")
        return NormalizedSubmitResult(
            accepted=bool(task_id),
            provider=self.provider_name,
            provider_model=str(model),
            provider_task_id=task_id or None,
            provider_status_raw=str(first_non_empty(data.get("code"), extract_nested(data, "data", "task_status"), "submitted")),
            callback_url_used=callback_url,
            raw_response=data,
            error_message=None if task_id else str(first_non_empty(data.get("message"), data.get("msg")) or "Kling did not return a task id"),
        )

    async def query(self, *, provider_task_id: str | None, provider_operation_name: str | None) -> NormalizedStatusResult:
        if provider_task_id and provider_task_id.startswith("kling-mock-task-"):
            return mock_query_result(self.provider_name)
        if not provider_task_id:
            raise ProviderConfigError("provider_task_id is required for Kling polling")
        if provider_mock_enabled() and not settings.kling_api_token:
            return mock_query_result(self.provider_name)

        path = settings.kling_text_to_video_status_path_template.format(task_id=provider_task_id)
        data = await request_json(
            method="GET",
            url=f"{settings.kling_api_base_url.rstrip('/')}{path}",
            headers=self._headers(),
        )
        raw_status = str(first_non_empty(
            extract_nested(data, "data", "task_status"),
            extract_nested(data, "data", "status"),
            data.get("status"),
            data.get("code"),
        ) or "")
        state = map_status_to_state(
            raw_status,
            processing={"submitted", "pending", "processing", "running", "queueing"},
            success={"succeed", "succeeded", "success", "completed"},
            failure={"failed", "error"},
            canceled={"canceled", "cancelled"},
        )
        output_url = first_non_empty(
            extract_nested(data, "data", "task_result", "videos", "0", "url"),
            extract_nested(data, "data", "video", "url"),
            extract_nested(data, "data", "video_url"),
        )
        thumbnail_url = first_non_empty(
            extract_nested(data, "data", "task_result", "videos", "0", "cover_url"),
            extract_nested(data, "data", "cover_url"),
        )
        return NormalizedStatusResult(
            provider=self.provider_name,
            state=state,
            provider_status_raw=raw_status or None,
            output_video_url=str(output_url) if output_url else None,
            output_thumbnail_url=str(thumbnail_url) if thumbnail_url else None,
            metadata={"task_id": provider_task_id},
            error_message=str(first_non_empty(extract_nested(data, "data", "task_status_msg"), data.get("message"), data.get("msg")) or "") or None,
            failure_code=str(data.get("code") or "") or None,
            failure_category="provider_poll" if state == "failed" else None,
            raw_response=data,
        )

    def verify_callback(self, headers: dict[str, str], raw_body: bytes) -> bool:
        return verify_hmac_signature(
            headers=headers,
            raw_body=raw_body,
            secret=settings.kling_callback_shared_secret or settings.provider_callback_shared_secret,
        )

    def normalize_callback(self, headers: dict[str, str], payload: dict) -> NormalizedCallbackEvent:
        data = payload.get("data", payload)
        raw_status = str(first_non_empty(data.get("task_status"), data.get("status"), payload.get("status")) or "")
        state = map_status_to_state(
            raw_status,
            processing={"submitted", "pending", "processing", "running", "queueing"},
            success={"succeed", "succeeded", "success", "completed"},
            failure={"failed", "error"},
            canceled={"canceled", "cancelled"},
        )
        return make_callback_event(
            provider=self.provider_name,
            payload=payload,
            event_type=str(payload.get("event") or "kling.task"),
            event_idempotency_key=str(first_non_empty(payload.get("request_id"), data.get("task_id"), data.get("id")) or "kling-unknown"),
            provider_task_id=str(first_non_empty(data.get("task_id"), data.get("id")) or "") or None,
            provider_status_raw=raw_status or None,
            state=state,
            output_video_url=str(first_non_empty(extract_nested(data, "task_result", "videos", "0", "url"), data.get("video_url")) or "") or None,
            output_thumbnail_url=str(first_non_empty(extract_nested(data, "task_result", "videos", "0", "cover_url"), data.get("cover_url")) or "") or None,
            error_message=str(first_non_empty(data.get("task_status_msg"), payload.get("message"), payload.get("msg")) or "") or None,
            failure_code=str(payload.get("code") or "") or None,
            failure_category="provider_callback" if state == "failed" else None,
            metadata={"source": "kling_callback"},
        )
