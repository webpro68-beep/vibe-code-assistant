from __future__ import annotations

from .types import PlannedScene


STYLE_HINTS = {
    "cinematic_dark": "cinematic realism, moody lighting, dramatic contrast, controlled camera movement",
    "documentary": "documentary realism, natural motion, observational camera, grounded details",
    "commercial": "clean composition, premium product lighting, polished motion design",
    "anime": "stylized animation, strong silhouettes, expressive motion, vivid composition",
}


def build_scene_prompt(scene: PlannedScene) -> str:
    style_hint = STYLE_HINTS.get(scene.style_preset or "", "cinematic realism, clean composition")
    base_text = (scene.visual_prompt or scene.script_text or "").strip()

    return (
        f"{base_text}. "
        f"Style: {style_hint}. "
        f"Shot intent: {scene.title}. "
        f"Keep the framing complete, subject fully visible, no crop errors."
    ).strip()