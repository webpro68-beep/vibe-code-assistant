from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IncidentStateSnapshot(BaseModel):
    incident_key: str
    job_id: str
    project_id: str
    provider: str
    incident_family: str
    current_event_id: str | None = None
    current_event_type: str | None = None
    current_severity_rank: int = 0
    first_seen_at: datetime
    last_seen_at: datetime
    last_transition_at: datetime
    status: str
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    assigned_to: str | None = None
    assigned_by: str | None = None
    assigned_at: datetime | None = None
    muted: bool = False
    muted_until: datetime | None = None
    muted_by: str | None = None
    mute_reason: str | None = None
    suppressed: bool = False
    suppression_reason: str | None = None
    reopen_count: int = 0
    last_reopened_at: datetime | None = None
    resolved_at: datetime | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class IncidentActionItem(BaseModel):
    id: str
    incident_key: str
    event_id: str | None = None
    job_id: str
    action_type: str
    actor: str
    reason: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class IncidentHistoryEventItem(BaseModel):
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
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class IncidentHistoryResponse(BaseModel):
    incident: IncidentStateSnapshot
    actions: list[IncidentActionItem] = Field(default_factory=list)
    timeline_events: list[IncidentHistoryEventItem] = Field(default_factory=list)
    projected_timeline: list[IncidentHistoryEventItem] = Field(default_factory=list)


class IncidentNoteUpdateRequest(BaseModel):
    actor: str
    note: str | None = None


class IncidentNoteResponse(BaseModel):
    ok: bool = True
    incident_key: str
    note: str | None = None
    updated_at: datetime
