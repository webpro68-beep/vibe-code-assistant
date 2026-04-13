from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class WorkerOverrideUpdateRequest(BaseModel):
    actor: str
    queue_name: str = "render.dispatch"
    dispatch_batch_limit: int | None = Field(default=None, ge=1, le=500)
    poll_countdown_seconds: int | None = Field(default=None, ge=5, le=3600)
    enabled: bool | None = None
    reason: str | None = None


class WorkerOverrideResponse(BaseModel):
    queue_name: str
    dispatch_batch_limit: int
    poll_countdown_seconds: int
    enabled: bool
    reason: str | None = None
    updated_by: str | None = None


class ProviderOverrideUpdateRequest(BaseModel):
    actor: str
    source_provider: str
    target_provider: str
    active: bool = True
    reason: str | None = None
    expires_at: datetime | None = None


class ProviderOverrideResponse(BaseModel):
    source_provider: str
    target_provider: str
    active: bool
    reason: str | None = None
    updated_by: str | None = None
    expires_at: datetime | None = None


class ReleaseGateUpdateRequest(BaseModel):
    actor: str
    blocked: bool
    reason: str | None = None
    source: str = "manual"


class ReleaseGateResponse(BaseModel):
    gate_name: str
    blocked: bool
    reason: str | None = None
    source: str | None = None
    updated_by: str | None = None
    last_decision_type: str | None = None


class DecisionAuditLogResponse(BaseModel):
    id: str
    decision_type: str
    actor: str
    execution_status: Literal["executed", "planned_only", "dry_run", "rejected"]
    reason: str | None = None
    action_payload_json: str | None = None
    result_json: str | None = None
    policy_version: str | None = None
    recommendation_key: str | None = None
    created_at: datetime
