from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RenderProvider = Literal["veo_3_1", "runway_gen4", "kling_3"]


@dataclass(frozen=True)
class ProviderCapabilities:
    provider: RenderProvider
    label: str
    default_scene_duration_sec: float
    max_scene_duration_sec: float
    supports_native_audio: bool
    supports_multi_shot_prompt: bool
    recommended_mode: str


PROVIDER_CAPABILITIES: dict[RenderProvider, ProviderCapabilities] = {
    "veo_3_1": ProviderCapabilities(
        provider="veo_3_1",
        label="Google Veo 3.1",
        default_scene_duration_sec=8.0,
        max_scene_duration_sec=8.0,
        supports_native_audio=True,
        supports_multi_shot_prompt=False,
        recommended_mode="cinematic_single_shot",
    ),
    "runway_gen4": ProviderCapabilities(
        provider="runway_gen4",
        label="Runway Gen-4",
        default_scene_duration_sec=5.0,
        max_scene_duration_sec=10.0,
        supports_native_audio=False,
        supports_multi_shot_prompt=False,
        recommended_mode="image_plus_motion_control",
    ),
    "kling_3": ProviderCapabilities(
        provider="kling_3",
        label="Kling 3",
        default_scene_duration_sec=5.0,
        max_scene_duration_sec=15.0,
        supports_native_audio=False,
        supports_multi_shot_prompt=True,
        recommended_mode="multi_shot_storyboard",
    ),
}


def get_provider_capabilities(provider: RenderProvider) -> ProviderCapabilities:
    if provider not in PROVIDER_CAPABILITIES:
        raise ValueError(f"Unsupported provider: {provider}")
    return PROVIDER_CAPABILITIES[provider]