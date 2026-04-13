from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class BulkActionAuditItem(BaseModel):
    incident_key: str
    ok: bool
    status: str | None = None
    error: str | None = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime


class BulkActionAuditRun(BaseModel):
    id: str
    action_type: str
    actor: str
    actor_role: str
    actor_team_id: str | None = None
    mode: str
    reason: str | None = None
    attempted: int
    succeeded: int
    failed: int
    filters: dict = Field(default_factory=dict)
    request: dict = Field(default_factory=dict)
    created_at: datetime


class BulkActionAuditListResponse(BaseModel):
    items: list[BulkActionAuditRun] = Field(default_factory=list)


class BulkActionAuditDetailResponse(BaseModel):
    run: BulkActionAuditRun
    items: list[BulkActionAuditItem] = Field(default_factory=list)
