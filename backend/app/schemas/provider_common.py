from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class NormalizedSubmitResult(BaseModel):
    """
    Kết quả chuẩn hóa sau khi submit scene sang provider.
    Được dùng bởi:
    - provider adapters
    - provider_router.submit_render_task(...)
    - render_dispatch_service.py
    - render_dispatch_worker.py
    """

    accepted: bool
    provider: str

    provider_model: str | None = None
    provider_request_id: str | None = None
    provider_task_id: str | None = None
    provider_operation_name: str | None = None
    provider_status_raw: str | None = None

    callback_url_used: str | None = None

    raw_response: dict[str, Any] | None = None
    error_message: str | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("provider must not be empty")
        return normalized

    @field_validator("raw_response")
    @classmethod
    def validate_raw_response(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None and not isinstance(value, dict):
            raise ValueError("raw_response must be a dict or None")
        return value


class NormalizedStatusResult(BaseModel):
    """
    Kết quả chuẩn hóa khi query/poll trạng thái provider.
    Được dùng bởi:
    - provider adapters
    - provider_router.query_render_task(...)
    - render_poll_service.py
    - render_poll_worker.py
    """

    provider: str
    state: str

    provider_status_raw: str | None = None

    output_video_url: str | None = None
    output_thumbnail_url: str | None = None

    metadata: dict[str, Any] | None = None

    error_message: str | None = None
    failure_code: str | None = None
    failure_category: str | None = None

    raw_response: dict[str, Any] | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("provider must not be empty")
        return normalized

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"processing", "succeeded", "failed", "canceled"}
        if normalized not in allowed:
            raise ValueError(f"state must be one of {sorted(allowed)}")
        return normalized

    @field_validator("metadata", "raw_response")
    @classmethod
    def validate_dict_fields(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if value is not None and not isinstance(value, dict):
            raise ValueError("metadata/raw_response must be a dict or None")
        return value


class NormalizedCallbackEvent(BaseModel):
    """
    Kết quả chuẩn hóa khi provider bắn callback/webhook về backend.
    Được dùng bởi:
    - provider adapters
    - provider_router.normalize_render_callback(...)
    - provider_callbacks.py
    """

    provider: str
    event_type: str | None = None
    event_idempotency_key: str

    provider_task_id: str | None = None
    provider_operation_name: str | None = None
    provider_status_raw: str | None = None

    state: str | None = None

    output_video_url: str | None = None
    output_thumbnail_url: str | None = None

    metadata: dict[str, Any] | None = None

    error_message: str | None = None
    failure_code: str | None = None
    failure_category: str | None = None

    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("provider must not be empty")
        return normalized

    @field_validator("event_idempotency_key")
    @classmethod
    def validate_event_idempotency_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("event_idempotency_key must not be empty")
        return normalized

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        allowed = {"processing", "succeeded", "failed", "canceled"}
        if normalized not in allowed:
            raise ValueError(f"state must be one of {sorted(allowed)}")
        return normalized

    @field_validator("metadata", "raw_payload")
    @classmethod
    def validate_dict_fields(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if value is not None and not isinstance(value, dict):
            raise ValueError("metadata/raw_payload must be a dict or None")
        return value