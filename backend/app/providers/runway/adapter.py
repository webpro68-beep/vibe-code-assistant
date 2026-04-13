
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


class RunwayAdapter(BaseVideoProviderAdapter):
    provider_name = "runway"

    def _headers(self) -> dict[str, str]:
        if not settings.runway_api_secret:
            raise ProviderConfigError("RUNWAYML_API_SECRET is not configured")
        return {
            "Authorization": f"Bearer {settings.runway_api_secret}",
            "X-Runway-Version": settings.runway_api_version,
            "Content-Type": "application/json",
        }

    def _build_submit_body(self, scene_payload: dict[str, Any]) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": scene_payload.get("provider_model") or settings.runway_default_model,
            "promptText": scene_payload.get("prompt_text") or "",
            "ratio": "720:1280" if scene_payload.get("aspect_ratio") == "9:16" else "1280:720" if scene_payload.get("aspect_ratio") == "16:9" else "1024:1024",
            "duration": int(scene_payload.get("duration_seconds") or 5),
        }
        prompt_image = scene_payload.get("prompt_image_url")
        if prompt_image:
            body["promptImage"] = prompt_image
        seed = scene_payload.get("seed")
        if seed is not None:
            body["seed"] = int(seed)
        return body

    async def submit(self, scene_payload: dict, callback_url: str | None) -> NormalizedSubmitResult:
        model = scene_payload.get("provider_model") or settings.runway_default_model
        if not settings.runway_api_secret and provider_mock_enabled():
            return mock_submit_result(
                provider=self.provider_name,
                model=model,
                callback_url=callback_url,
                reason="RUNWAYML_API_SECRET missing; using mock fallback",
            )

        payload = self._build_submit_body(scene_payload)
        data = await request_json(
            method="POST",
            url=f"{settings.runway_api_base_url.rstrip('/')}/v1/image_to_video",
            headers=self._headers(),
            json_body=payload,
        )
        task_id = str(first_non_empty(data.get("id"), data.get("taskId"), extract_nested(data, "task", "id")) or "")
        return NormalizedSubmitResult(
            accepted=bool(task_id),
            provider=self.provider_name,
            provider_model=str(payload["model"]),
            provider_task_id=task_id or None,
            provider_status_raw=str(first_non_empty(data.get("status"), "PENDING")),
            callback_url_used=callback_url,
            raw_response=data,
            error_message=None if task_id else "Runway did not return a task id",
        )

    async def query(self, *, provider_task_id: str | None, provider_operation_name: str | None) -> NormalizedStatusResult:
        if provider_task_id and provider_task_id.startswith("runway-mock-task-"):
            return mock_query_result(self.provider_name)
        if not provider_task_id:
            raise ProviderConfigError("provider_task_id is required for Runway polling")
        if not settings.runway_api_secret and provider_mock_enabled():
            return mock_query_result(self.provider_name)

        data = await request_json(
            method="GET",
            url=f"{settings.runway_api_base_url.rstrip('/')}/v1/tasks/{provider_task_id}",
            headers=self._headers(),
        )
        raw_status = str(first_non_empty(data.get("status"), extract_nested(data, "task", "status"), "PENDING"))
        state = map_status_to_state(
            raw_status,
            processing={"pending", "queued", "running", "processing", "in_progress"},
            success={"succeeded", "success", "completed"},
            failure={"failed", "error"},
            canceled={"canceled", "cancelled"},
        )
        output_url = first_non_empty(
            extract_nested(data, "output", "0"),
            extract_nested(data, "artifacts", "0", "url"),
            data.get("outputUrl"),
        )
        thumbnail_url = first_non_empty(
            extract_nested(data, "artifacts", "0", "thumbnailUrl"),
            data.get("thumbnailUrl"),
        )
        return NormalizedStatusResult(
            provider=self.provider_name,
            state=state,
            provider_status_raw=raw_status,
            output_video_url=str(output_url) if output_url else None,
            output_thumbnail_url=str(thumbnail_url) if thumbnail_url else None,
            metadata={"task_id": provider_task_id},
            error_message=str(first_non_empty(data.get("error"), extract_nested(data, "failure", "message")) or "") or None,
            failure_code=str(first_non_empty(extract_nested(data, "failure", "code"), data.get("errorCode")) or "") or None,
            failure_category="provider_poll" if state == "failed" else None,
            raw_response=data,
        )

    def verify_callback(self, headers: dict[str, str], raw_body: bytes) -> bool:
        return verify_hmac_signature(
            headers=headers,
            raw_body=raw_body,
            secret=settings.runway_callback_shared_secret or settings.provider_callback_shared_secret,
        )

    def normalize_callback(self, headers: dict[str, str], payload: dict) -> NormalizedCallbackEvent:
        raw_status = str(first_non_empty(payload.get("status"), payload.get("state"), ""))
        state = map_status_to_state(
            raw_status,
            processing={"pending", "queued", "running", "processing", "in_progress"},
            success={"succeeded", "success", "completed"},
            failure={"failed", "error"},
            canceled={"canceled", "cancelled"},
        )
        return make_callback_event(
            provider=self.provider_name,
            payload=payload,
            event_type=str(payload.get("type") or payload.get("event") or "runway.task"),
            event_idempotency_key=str(first_non_empty(payload.get("id"), payload.get("eventId"), payload.get("taskId")) or "runway-unknown"),
            provider_task_id=str(payload.get("taskId") or payload.get("id") or "") or None,
            provider_status_raw=raw_status or None,
            state=state,
            output_video_url=str(first_non_empty(payload.get("output_video_url"), payload.get("outputUrl"), extract_nested(payload, "output", "0")) or "") or None,
            output_thumbnail_url=str(payload.get("thumbnailUrl") or "") or None,
            error_message=str(first_non_empty(payload.get("error"), extract_nested(payload, "failure", "message")) or "") or None,
            failure_code=str(first_non_empty(extract_nested(payload, "failure", "code"), payload.get("errorCode")) or "") or None,
            failure_category="provider_callback" if state == "failed" else None,
            metadata={"source": "runway_callback"},
        )
