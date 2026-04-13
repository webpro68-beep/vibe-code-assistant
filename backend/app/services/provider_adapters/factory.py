from __future__ import annotations

from .types import PlannedScene, ProviderRenderPayload
from .veo_adapter import adapt_scene_to_veo
from .runway_adapter import adapt_scene_to_runway
from .kling_adapter import adapt_scene_to_kling


def build_provider_payload(scene: PlannedScene, provider: str) -> ProviderRenderPayload:
    if provider == "veo_3_1":
        return adapt_scene_to_veo(scene)

    if provider == "runway_gen4_turbo":
        return adapt_scene_to_runway(scene)

    if provider in {"kling_text", "kling_image"}:
        return adapt_scene_to_kling(scene)

    raise ValueError(f"Unsupported provider: {provider}")