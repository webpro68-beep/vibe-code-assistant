from __future__ import annotations

from .factory import build_provider_payload
from .types import PlannedScene


def build_render_payloads(*, planned_scenes: list[dict], provider: str, aspect_ratio: str, style_preset: str | None = None):
    outputs = []
    for scene in planned_scenes:
        normalized = {
            **scene,
            "aspect_ratio": scene.get("aspect_ratio") or aspect_ratio,
            "style_preset": scene.get("style_preset") or style_preset,
        }
        outputs.append(build_provider_payload(PlannedScene(**normalized), provider).model_dump())
    return outputs
