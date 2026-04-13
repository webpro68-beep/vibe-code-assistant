
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.provider_common import (
    NormalizedCallbackEvent,
    NormalizedStatusResult,
    NormalizedSubmitResult,
)


class ProviderConfigError(RuntimeError):
    pass


class ProviderHTTPError(RuntimeError):
    pass


def canonical_json(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def verify_hmac_signature(
    *,
    headers: dict[str, str],
    raw_body: bytes,
    secret: str | None,
    signature_header: str = "x-render-signature",
) -> bool:
    if not secret:
        return True
    provided = (headers.get(signature_header) or "").strip()
    if not provided:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    normalized = provided.removeprefix("sha256=").strip()
    return hmac.compare_digest(normalized, expected)


def retry_delay_seconds(attempt: int) -> float:
    base = max(0.1, float(settings.provider_retry_base_seconds))
    return base * (2 ** max(0, attempt - 1))


async def request_json(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    timeout = timeout_seconds or settings.provider_http_timeout_seconds
    retries = max(0, settings.provider_max_retries)

    last_error: Exception | None = None
    for attempt in range(1, retries + 2):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    json=json_body,
                    params=params,
                )
            if response.status_code in {429, 500, 502, 503, 504} and attempt <= retries:
                await sleep_backoff(attempt)
                continue
            response.raise_for_status()
            if not response.content:
                return {}
            payload = response.json()
            return payload if isinstance(payload, dict) else {"data": payload}
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            if attempt <= retries:
                await sleep_backoff(attempt)
                continue
            break

    raise ProviderHTTPError(str(last_error) if last_error else f"{method} {url} failed")


async def sleep_backoff(attempt: int) -> None:
    import asyncio
    await asyncio.sleep(retry_delay_seconds(attempt))


def provider_mock_enabled() -> bool:
    return bool(settings.provider_allow_mock_fallback)


def mock_submit_result(
    *,
    provider: str,
    model: str | None,
    callback_url: str | None,
    use_operation: bool = False,
    reason: str,
) -> NormalizedSubmitResult:
    suffix = str(int(time.time() * 1000))
    return NormalizedSubmitResult(
        accepted=True,
        provider=provider,
        provider_model=model,
        provider_task_id=None if use_operation else f"{provider}-mock-task-{suffix}",
        provider_operation_name=f"operations/{provider}-mock-{suffix}" if use_operation else None,
        provider_status_raw="MOCK_SUBMITTED",
        callback_url_used=callback_url,
        raw_response={"mock": True, "reason": reason},
    )


def mock_query_result(provider: str) -> NormalizedStatusResult:
    return NormalizedStatusResult(
        provider=provider,
        state="succeeded",
        provider_status_raw="MOCK_SUCCEEDED",
        metadata={"mock": True},
        raw_response={"mock": True},
    )


def map_status_to_state(status: str | None, *, processing: set[str], success: set[str], failure: set[str], canceled: set[str]) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in success:
        return "succeeded"
    if normalized in failure:
        return "failed"
    if normalized in canceled:
        return "canceled"
    return "processing"


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def extract_nested(payload: Any, *path: str) -> Any:
    current = payload
    for key in path:
        if isinstance(current, list):
            try:
                current = current[int(key)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            if key not in current:
                return None
            current = current[key]
        else:
            return None
    return current


def make_callback_event(
    *,
    provider: str,
    payload: dict[str, Any],
    event_idempotency_key: str,
    event_type: str | None = None,
    provider_task_id: str | None = None,
    provider_operation_name: str | None = None,
    provider_status_raw: str | None = None,
    state: str | None = None,
    output_video_url: str | None = None,
    output_thumbnail_url: str | None = None,
    error_message: str | None = None,
    failure_code: str | None = None,
    failure_category: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> NormalizedCallbackEvent:
    return NormalizedCallbackEvent(
        provider=provider,
        event_type=event_type,
        event_idempotency_key=event_idempotency_key,
        provider_task_id=provider_task_id,
        provider_operation_name=provider_operation_name,
        provider_status_raw=provider_status_raw,
        state=state,
        output_video_url=output_video_url,
        output_thumbnail_url=output_thumbnail_url,
        error_message=error_message,
        failure_code=failure_code,
        failure_category=failure_category,
        metadata=metadata,
        raw_payload=payload,
    )
