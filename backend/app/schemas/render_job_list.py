from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class RenderJobListItem(BaseModel):
    id: str
    project_id: str
    provider: str
    status: str
    health_status: str | None = None
    health_reason: str | None = None
    aspect_ratio: str
    style_preset: str | None = None
    subtitle_mode: str | None = None
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


class RenderJobListPage(BaseModel):
    items: list[RenderJobListItem] = Field(default_factory=list)
    total: int
    limit: int
