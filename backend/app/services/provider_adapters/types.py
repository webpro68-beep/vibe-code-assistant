from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


AdapterKind = Literal["google_gemini", "runway", "kling"]
ProviderMode = Literal["text_to_video", "image_to_video", "first_last_frames", "reference_image_to_video"]


@dataclass
class PlannedScene:
    scene_index: int
    title: str
    script_text: str
    provider_target_duration_sec: float
    aspect_ratio: str
    style_preset: str | None = None
    source_scene_index: int | None = None
    visual_prompt: str | None = None
    start_image_url: str | None = None
    end_image_url: str | None = None
    provider_mode: ProviderMode | None = None
    character_reference_pack_id: str | None = None
    character_reference_image_urls: list[str] | None = None


@dataclass
class ProviderRenderPayload:
    provider: str
    adapter_kind: AdapterKind
    endpoint: str
    model: str
    body: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)