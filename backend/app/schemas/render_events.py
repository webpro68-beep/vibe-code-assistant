from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RenderEventItem(BaseModel):
    id: str
    source: str
    event_type: str
    job_id: str
    scene_task_id: str | None = None
    scene_index: int | None = None
    provider: str | None = None
    status: str | None = None
    provider_status_raw: str | None = None
    failure_code: str | None = None
    failure_category: str | None = None
    error_message: str | None = None
    provider_task_id: str | None = None
    provider_operation_name: str | None = None
    provider_request_id: str | None = None
    signature_valid: bool | None = None
    processed: bool | None = None
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class RenderEventsResponse(BaseModel):
    items: list[RenderEventItem] = Field(default_factory=list)
    total: int
