from __future__ import annotations

from app.providers.base import BaseVideoProviderAdapter
from app.providers.kling.adapter import KlingAdapter
from app.providers.runway.adapter import RunwayAdapter
from app.providers.veo.adapter import VeoAdapter
from app.schemas.provider_common import (
    NormalizedCallbackEvent,
    NormalizedStatusResult,
    NormalizedSubmitResult,
)


_ADAPTER_CACHE: dict[str, BaseVideoProviderAdapter] = {}


def _normalize_provider_name(provider: str) -> str:
    value = provider.strip().lower()

    aliases = {
        "veo": "veo",
        "veo_3": "veo",
        "veo_3_1": "veo",
        "google_veo": "veo",
        "runway": "runway",
        "runwayml": "runway",
        "kling": "kling",
        "klingai": "kling",
    }

    return aliases.get(value, value)


def get_provider_adapter(provider: str) -> BaseVideoProviderAdapter:
    provider_key = _normalize_provider_name(provider)

    if provider_key in _ADAPTER_CACHE:
        return _ADAPTER_CACHE[provider_key]

    if provider_key == "veo":
        adapter: BaseVideoProviderAdapter = VeoAdapter()
    elif provider_key == "runway":
        adapter = RunwayAdapter()
    elif provider_key == "kling":
        adapter = KlingAdapter()
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    _ADAPTER_CACHE[provider_key] = adapter
    return adapter


async def submit_render_task(
    *,
    provider: str,
    scene_payload: dict,
    callback_url: str | None,
) -> NormalizedSubmitResult:
    normalized_provider = _normalize_provider_name(provider)

    try:
        adapter = get_provider_adapter(normalized_provider)
        result = await adapter.submit(
            scene_payload=scene_payload,
            callback_url=callback_url,
        )

        return NormalizedSubmitResult(
            accepted=result.accepted,
            provider=result.provider or normalized_provider,
            provider_model=result.provider_model,
            provider_request_id=result.provider_request_id,
            provider_task_id=result.provider_task_id,
            provider_operation_name=result.provider_operation_name,
            provider_status_raw=result.provider_status_raw,
            callback_url_used=result.callback_url_used or callback_url,
            raw_response=result.raw_response,
            error_message=result.error_message,
        )
    except Exception as exc:
        return NormalizedSubmitResult(
            accepted=False,
            provider=normalized_provider,
            provider_model=scene_payload.get("provider_model"),
            callback_url_used=callback_url,
            raw_response=None,
            error_message=str(exc),
        )


async def query_render_task(
    *,
    provider: str,
    provider_task_id: str | None,
    provider_operation_name: str | None,
) -> NormalizedStatusResult:
    normalized_provider = _normalize_provider_name(provider)

    try:
        adapter = get_provider_adapter(normalized_provider)
        result = await adapter.query(
            provider_task_id=provider_task_id,
            provider_operation_name=provider_operation_name,
        )

        return NormalizedStatusResult(
            provider=result.provider or normalized_provider,
            state=result.state,
            provider_status_raw=result.provider_status_raw,
            output_video_url=result.output_video_url,
            output_thumbnail_url=result.output_thumbnail_url,
            metadata=result.metadata,
            error_message=result.error_message,
            failure_code=result.failure_code,
            failure_category=result.failure_category,
            raw_response=result.raw_response,
        )
    except Exception as exc:
        return NormalizedStatusResult(
            provider=normalized_provider,
            state="failed",
            provider_status_raw=None,
            output_video_url=None,
            output_thumbnail_url=None,
            metadata=None,
            error_message=str(exc),
            failure_code="PROVIDER_ROUTER_QUERY_EXCEPTION",
            failure_category="provider_poll",
            raw_response=None,
        )


def verify_render_callback(
    *,
    provider: str,
    headers: dict[str, str],
    raw_body: bytes,
) -> bool:
    normalized_provider = _normalize_provider_name(provider)

    try:
        adapter = get_provider_adapter(normalized_provider)
        return bool(adapter.verify_callback(headers, raw_body))
    except Exception:
        return False


def normalize_render_callback(
    *,
    provider: str,
    headers: dict[str, str],
    payload: dict,
) -> NormalizedCallbackEvent:
    normalized_provider = _normalize_provider_name(provider)

    adapter = get_provider_adapter(normalized_provider)
    result = adapter.normalize_callback(headers, payload)

    return NormalizedCallbackEvent(
        provider=result.provider or normalized_provider,
        event_type=result.event_type,
        event_idempotency_key=result.event_idempotency_key,
        provider_task_id=result.provider_task_id,
        provider_operation_name=result.provider_operation_name,
        provider_status_raw=result.provider_status_raw,
        state=result.state,
        output_video_url=result.output_video_url,
        output_thumbnail_url=result.output_thumbnail_url,
        metadata=result.metadata,
        error_message=result.error_message,
        failure_code=result.failure_code,
        failure_category=result.failure_category,
        raw_payload=result.raw_payload,
    )