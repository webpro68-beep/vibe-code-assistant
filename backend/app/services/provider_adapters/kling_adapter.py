from __future__ import annotations

from .types import PlannedScene, ProviderRenderPayload
from .prompt_normalizer import build_scene_prompt


_ALLOWED_KLING_RATIOS = {"16:9", "9:16", "1:1"}


def _nearest_kling_duration(value: float) -> int:
    # safest public baseline for common text/image video calls
    return 10 if value > 7.5 else 5


def adapt_scene_to_kling(scene: PlannedScene) -> ProviderRenderPayload:
    if scene.aspect_ratio not in _ALLOWED_KLING_RATIOS:
        raise ValueError(f"Unsupported Kling aspect ratio: {scene.aspect_ratio}")

    prompt = build_scene_prompt(scene)
    duration = _nearest_kling_duration(scene.provider_target_duration_sec)

    if scene.start_image_url:
        endpoint = "/text2video/image-to-video"
        body = {
            "model": "kling-v1",
            "image": scene.start_image_url,
            "prompt": prompt,
            "aspect_ratio": scene.aspect_ratio,
            "duration": str(duration),
        }
        provider = "kling_image"
    else:
        endpoint = "/text2video/text-to-video"
        body = {
            "model": "kling-v1",
            "prompt": prompt,
            "aspect_ratio": scene.aspect_ratio,
            "duration": str(duration),
        }
        provider = "kling_text"

    return ProviderRenderPayload(
        provider=provider,
        adapter_kind="kling",
        endpoint=endpoint,
        model=body["model"],
        body=body,
        metadata={
            "supports_native_audio": False,
            "duration_policy": "rounded_to_5_or_10",
        },
    )