from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlannedSceneInput(BaseModel):
    scene_index: int
    title: str
    script_text: str
    provider_target_duration_sec: float

    target_duration_sec: float | None = None
    provider_mode: str | None = None
    source_scene_index: int | None = None
    visual_prompt: str | None = None
    start_image_url: str | None = None
    end_image_url: str | None = None


class CreateRenderJobRequest(BaseModel):
    project_id: str
    provider: str
    aspect_ratio: str = Field(default="16:9")
    style_preset: str | None = None
    subtitle_mode: str | None = None
    planned_scenes: list[PlannedSceneInput]