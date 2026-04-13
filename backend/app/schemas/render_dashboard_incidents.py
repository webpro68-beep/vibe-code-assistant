from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class IncidentJobSnapshot(BaseModel):
    job_id: str
    project_id: str
    provider: str
    status: str
    health_status: str | None = None
    health_reason: str | None = None
    planned_scene_count: int
    processing_scene_count: int
    succeeded_scene_count: int
    failed_scene_count_snapshot: int
    stalled_scene_count: int
    degraded_scene_count: int
    active_scene_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_event_at: datetime | None = None
    last_health_transition_at: datetime | None = None


class RecentIncidentItem(BaseModel):
    event_id: str
    incident_key: str
    event_type: str
    occurred_at: datetime
    previous_status: str | None = None
    current_status: str | None = None
    previous_reason: str | None = None
    current_reason: str | None = None
    workflow_status: str | None = None
    acknowledged: bool = False
    muted: bool = False
    assigned_to: str | None = None
    job: IncidentJobSnapshot
    payload: dict = Field(default_factory=dict)


class RecentIncidentsResponse(BaseModel):
    items: list[RecentIncidentItem] = Field(default_factory=list)
    limit: int
    total_returned: int
    next_cursor: str | None = None
