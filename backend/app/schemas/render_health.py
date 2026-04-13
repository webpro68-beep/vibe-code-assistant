from __future__ import annotations

from pydantic import BaseModel, Field


class RenderJobHealthSummary(BaseModel):
    status: str
    reason: str | None = None
    total_scenes: int
    queued_scenes: int
    processing_scenes: int
    succeeded_scenes: int
    failed_scenes: int
    stalled_scenes: int
    degraded_scenes: int
    last_event_at: str | None = None
    active_scene_ids: list[str] = Field(default_factory=list)
    stalled_scene_ids: list[str] = Field(default_factory=list)
    degraded_scene_ids: list[str] = Field(default_factory=list)
