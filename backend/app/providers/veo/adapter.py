
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.providers.base import BaseVideoProviderAdapter
from app.providers.common import (
    ProviderConfigError,
    extract_nested,
    first_non_empty,
    make_callback_event,
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


class VeoAdapter(BaseVideoProviderAdapter):
    provider_name = "veo"

    def _veo_mode(self, scene_payload: dict[str, Any]) -> str:
        mode = str(scene_payload.get("veo_mode") or scene_payload.get("provider_mode") or "").strip().lower()
        if mode:
            return mode
        if scene_payload.get("start_image_url") and scene_payload.get("end_image_url"):
            return "first_last_frames"
        if scene_payload.get("start_image_url"):
            return "image_to_video"
        return "text_to_video"

    def _model(self, scene_payload: dict[str, Any]) -> str:
        return str(scene_payload.get("provider_model") or settings.veo_default_model)

    def _gemini_submit_url(self, model: str) -> str:
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predictLongRunning"

    def _gemini_query_url(self, operation_name: str) -> str:
        return f"https://generativelanguage.googleapis.com/v1beta/{operation_name.lstrip('/')}"

    def _gemini_headers(self) -> dict[str, str]:
        if not settings.gemini_api_key:
            raise ProviderConfigError("GEMINI_API_KEY is required when GOOGLE_GENAI_USE_VERTEX=false")
        return {
            "x-goog-api-key": settings.gemini_api_key,
            "Content-Type": "application/json",
        }

    def _vertex_headers(self) -> dict[str, str]:
        try:
            import google.auth
            from google.auth.transport.requests import Request
        except Exception as exc:
            raise ProviderConfigError(f"google-auth is required for Vertex transport: {exc}") from exc

        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials, _ = google.auth.default(scopes=scopes)
        credentials.refresh(Request())
        return {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _vertex_submit_url(self, model: str) -> str:
        if not settings.google_cloud_project:
            raise ProviderConfigError("GOOGLE_CLOUD_PROJECT is required for Vertex Veo")
        location = settings.google_cloud_location
        project = settings.google_cloud_project
        return f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:predictLongRunning"

    def _vertex_query_url(self, model: str) -> str:
        if not settings.google_cloud_project:
            raise ProviderConfigError("GOOGLE_CLOUD_PROJECT is required for Vertex Veo")
        location = settings.google_cloud_location
        project = settings.google_cloud_project
        return f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:fetchPredictOperation"

    def _build_instance(self, scene_payload: dict[str, Any]) -> dict[str, Any]:
        mode = self._veo_mode(scene_payload)
        instance: dict[str, Any] = {"prompt": scene_payload.get("prompt_text") or ""}
        if mode == "image_to_video" and scene_payload.get("start_image_url"):
            instance["image"] = {"gcsUri": scene_payload.get("start_image_url")}
        elif mode == "first_last_frames" and scene_payload.get("start_image_url") and scene_payload.get("end_image_url"):
            instance["firstFrame"] = {"gcsUri": scene_payload.get("start_image_url")}
            instance["lastFrame"] = {"gcsUri": scene_payload.get("end_image_url")}
        elif mode == "reference_image_to_video":
            if scene_payload.get("start_image_url"):
                instance["image"] = {"gcsUri": scene_payload.get("start_image_url")}
            refs = scene_payload.get("character_reference_image_urls") or []
            if refs:
                instance["referenceImages"] = [{"gcsUri": uri} for uri in refs]
        elif mode == "text_to_video":
            refs = scene_payload.get("character_reference_image_urls") or []
            if refs:
                instance["metadata"] = {"characterReferenceImageUrls": refs}
        return instance

    def _build_parameters(self, scene_payload: dict[str, Any]) -> dict[str, Any]:
        mode = self._veo_mode(scene_payload)
        params: dict[str, Any] = {
            "aspectRatio": scene_payload.get("aspect_ratio") or "16:9",
            "durationSeconds": int(scene_payload.get("duration_seconds") or 4),
            "sampleCount": 1,
        }
        resolution = scene_payload.get("resolution")
        if resolution:
            params["resolution"] = resolution
        if settings.veo_output_gcs_uri:
            params["storageUri"] = settings.veo_output_gcs_uri
        if mode == "reference_image_to_video" and settings.veo_reference_preview_model:
            params["previewReferenceMode"] = True
        if scene_payload.get("sound_generation"):
            params["generateAudio"] = True
        return params

    async def submit(self, scene_payload: dict, callback_url: str | None) -> NormalizedSubmitResult:
        model = str(scene_payload.get("provider_model") or self._model(scene_payload))
        if provider_mock_enabled() and not settings.gemini_api_key and not settings.google_cloud_project:
            return mock_submit_result(
                provider=self.provider_name,
                model=model,
                callback_url=callback_url,
                use_operation=True,
                reason="No Veo credentials configured; using mock fallback",
            )

        body = {
            "instances": [self._build_instance(scene_payload)],
            "parameters": self._build_parameters(scene_payload),
        }

        if settings.google_genai_use_vertex:
            data = await request_json(
                method="POST",
                url=self._vertex_submit_url(model),
                headers=self._vertex_headers(),
                json_body=body,
            )
        else:
            data = await request_json(
                method="POST",
                url=self._gemini_submit_url(model),
                headers=self._gemini_headers(),
                json_body=body,
            )

        operation_name = str(first_non_empty(data.get("name"), data.get("operation"), extract_nested(data, "data", "name")) or "")
        return NormalizedSubmitResult(
            accepted=bool(operation_name),
            provider=self.provider_name,
            provider_model=model,
            provider_operation_name=operation_name or None,
            provider_status_raw="SUBMITTED",
            callback_url_used=callback_url,
            raw_response=data,
            error_message=None if operation_name else "Veo did not return an operation name",
        )

    async def query(self, *, provider_task_id: str | None, provider_operation_name: str | None) -> NormalizedStatusResult:
        if provider_operation_name and provider_operation_name.startswith("operations/veo-mock-"):
            return mock_query_result(self.provider_name)
        if not provider_operation_name:
            raise ProviderConfigError("provider_operation_name is required for Veo polling")

        if settings.google_genai_use_vertex:
            model = provider_operation_name.split("/models/")[1].split("/operations/")[0] if "/models/" in provider_operation_name else settings.veo_default_model
            data = await request_json(
                method="POST",
                url=self._vertex_query_url(model),
                headers=self._vertex_headers(),
                json_body={"operationName": provider_operation_name},
            )
        else:
            data = await request_json(
                method="GET",
                url=self._gemini_query_url(provider_operation_name),
                headers=self._gemini_headers(),
            )

        done = bool(data.get("done"))
        error = data.get("error")
        output_uri = first_non_empty(
            extract_nested(data, "response", "generateVideoResponse", "generatedSamples", "0", "video", "uri"),
            extract_nested(data, "response", "generated_videos", "0", "video", "uri"),
            extract_nested(data, "response", "videos", "0", "uri"),
        )
        if error:
            state = "failed"
        elif not done:
            state = "processing"
        elif output_uri:
            state = "succeeded"
        else:
            state = "processing"

        return NormalizedStatusResult(
            provider=self.provider_name,
            state=state,
            provider_status_raw="DONE" if done else "RUNNING",
            output_video_url=str(output_uri) if output_uri else None,
            output_thumbnail_url=None,
            metadata={"operation_name": provider_operation_name, "done": done},
            error_message=str(first_non_empty(extract_nested(error or {}, "message"), data.get("message")) or "") or None,
            failure_code=str(first_non_empty(extract_nested(error or {}, "code"), data.get("code")) or "") or None,
            failure_category="provider_poll" if state == "failed" else None,
            raw_response=data,
        )

    def verify_callback(self, headers: dict[str, str], raw_body: bytes) -> bool:
        return verify_hmac_signature(
            headers=headers,
            raw_body=raw_body,
            secret=settings.provider_callback_shared_secret,
        )

    def normalize_callback(self, headers: dict[str, str], payload: dict) -> NormalizedCallbackEvent:
        done = bool(payload.get("done"))
        error = payload.get("error")
        output_uri = first_non_empty(
            extract_nested(payload, "response", "generateVideoResponse", "generatedSamples", "0", "video", "uri"),
            extract_nested(payload, "response", "generated_videos", "0", "video", "uri"),
        )
        state = "failed" if error else "succeeded" if done and output_uri else "processing"
        return make_callback_event(
            provider=self.provider_name,
            payload=payload,
            event_type=str(payload.get("type") or "veo.operation"),
            event_idempotency_key=str(first_non_empty(payload.get("event_id"), payload.get("name"), payload.get("operation")) or "veo-unknown"),
            provider_operation_name=str(first_non_empty(payload.get("name"), payload.get("operation")) or "") or None,
            provider_status_raw="DONE" if done else "RUNNING",
            state=state,
            output_video_url=str(output_uri) if output_uri else None,
            error_message=str(first_non_empty(extract_nested(error or {}, "message"), payload.get("message")) or "") or None,
            failure_code=str(first_non_empty(extract_nested(error or {}, "code"), payload.get("code")) or "") or None,
            failure_category="provider_callback" if state == "failed" else None,
            metadata={"source": "veo_callback"},
        )
