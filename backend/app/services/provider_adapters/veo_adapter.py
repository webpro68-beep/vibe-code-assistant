from __future__ import annotations

from .types import PlannedScene, ProviderRenderPayload
from .prompt_normalizer import build_scene_prompt


_ALLOWED_DURATIONS = {4, 6, 8}
_ALLOWED_RATIOS = {"16:9", "9:16"}


def _nearest_veo_duration(value: float) -> int:
    target = min(_ALLOWED_DURATIONS, key=lambda x: abs(x - value))
    return int(target)


def adapt_scene_to_veo(scene: PlannedScene) -> ProviderRenderPayload:
    if scene.aspect_ratio not in _ALLOWED_RATIOS:
        raise ValueError(f"Unsupported Veo aspect ratio: {scene.aspect_ratio}")

    prompt = build_scene_prompt(scene)
    duration = _nearest_veo_duration(scene.provider_target_duration_sec)

    mode = scene.provider_mode or ("first_last_frames" if scene.start_image_url and scene.end_image_url else "image_to_video" if scene.start_image_url else "text_to_video")
    model = "veo-3.1-generate-001"
    body = {
        "model": model,
        "prompt": prompt,
        "config": {
            "durationSeconds": duration,
            "aspectRatio": scene.aspect_ratio,
            "resolution": "720p",
        },
    }

    if mode == "image_to_video" and scene.start_image_url:
        body["image"] = {
            "uri": scene.start_image_url,
            "mimeType": "image/png",
        }
    elif mode == "first_last_frames" and scene.start_image_url and scene.end_image_url:
        body["firstFrame"] = {"uri": scene.start_image_url, "mimeType": "image/png"}
        body["lastFrame"] = {"uri": scene.end_image_url, "mimeType": "image/png"}
    elif mode == "reference_image_to_video" and scene.start_image_url:
        body["image"] = {
            "uri": scene.start_image_url,
            "mimeType": "image/png",
        }
        if scene.character_reference_image_urls:
            body["referenceImages"] = [{"uri": u, "mimeType": "image/png"} for u in scene.character_reference_image_urls]
        model = "veo-3.1-generate-preview"
        body["model"] = model

    if scene.character_reference_image_urls and mode == "text_to_video":
        body["metadata"] = {"characterReferenceImageUrls": scene.character_reference_image_urls}

    return ProviderRenderPayload(
        provider="veo_3_1",
        adapter_kind="google_gemini",
        endpoint="models.generateVideos",
        model=model,
        body=body,
        metadata={
            "supports_native_audio": True,
            "duration_policy": "rounded_to_4_6_8",
            "veo_mode": mode,
        },
    )