from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RenderSceneTaskStatusData(BaseModel):
    id: str
    job_id: str
    scene_index: int
    title: str | None = None
    status: str
    provider_task_id: str | None = None
    provider_operation_name: str | None = None
    output_url: str | None = None
    output_path: str | None = None
    error_message: str | None = None
    completed_at: datetime | None = None


class RenderJobStatusData(BaseModel):
    id: str
    project_id: str
    provider: str
    aspect_ratio: str
    style_preset: str | None = None
    subtitle_mode: str | None = None

    status: str
    error_message: str | None = None

    planned_scene_count: int = 0

    output_url: str | None = None
    output_path: str | None = None
    storage_key: str | None = None
    thumbnail_url: str | None = None

    subtitle_segments: list[dict[str, Any]] | dict[str, Any] | None = None
    final_timeline: list[dict[str, Any]] | dict[str, Any] | None = None

    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    scenes: list[RenderSceneTaskStatusData] = Field(default_factory=list)


class RenderJobStatusResponse(BaseModel):
    ok: bool
    data: RenderJobStatusData
    error: str | None = None
    meta: dict[str, Any] | None = None