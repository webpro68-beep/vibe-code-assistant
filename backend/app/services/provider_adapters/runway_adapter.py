from __future__ import annotations

from .types import PlannedScene, ProviderRenderPayload
from .prompt_normalizer import build_scene_prompt


_RUNWAY_RATIO_MAP = {
    "16:9": "1280:720",
    "9:16": "720:1280",
    "1:1": "960:960",
}


def _nearest_runway_duration(value: float) -> int:
    # conservative default for Gen-4 style workflows
    return 10 if value > 7.5 else 5


def adapt_scene_to_runway(scene: PlannedScene) -> ProviderRenderPayload:
    ratio = _RUNWAY_RATIO_MAP.get(scene.aspect_ratio)
    if not ratio:
        raise ValueError(f"Unsupported Runway aspect ratio: {scene.aspect_ratio}")

    prompt = build_scene_prompt(scene)
    duration = _nearest_runway_duration(scene.provider_target_duration_sec)

    # safest baseline: image_to_video if start image exists, else text_to_video-style task
    if scene.start_image_url:
        endpoint = "/v1/image_to_video"
        body = {
            "model": "gen4_turbo",
            "promptText": prompt,
            "promptImage": scene.start_image_url,
            "ratio": ratio,
            "duration": duration,
        }
    else:
        # This follows the current SDK/docs pattern for text-to-video capable models
        endpoint = "client.textToVideo.create"
        body = {
            "model": "gen4.5",
            "promptText": prompt,
            "ratio": ratio,
            "duration": duration,
        }

    return ProviderRenderPayload(
        provider="runway_gen4_turbo",
        adapter_kind="runway",
        endpoint=endpoint,
        model=body["model"],
        body=body,
        metadata={
            "supports_native_audio": False,
            "duration_policy": "rounded_to_5_or_10",
            "ratio_format": "pixel_ratio_string",
        },
    )