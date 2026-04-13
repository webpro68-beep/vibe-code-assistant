from __future__ import annotations

from typing import Any

from app.services.script_ingestion import (
    build_subtitle_segments_from_scenes,
    estimate_duration,
)
from app.services.script_preview_validation import (
    rebuild_script_text_from_scenes,
    validate_edited_preview_payload,
)


def recalculate_scene_durations(
    scenes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    recalculated: list[dict[str, Any]] = []

    for scene in scenes:
        script_text = (scene.get("script_text") or "").strip()
        updated = {
            **scene,
            "target_duration_sec": estimate_duration(script_text),
        }
        recalculated.append(updated)

    return recalculated


def rebuild_subtitles_from_scenes(
    scenes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return build_subtitle_segments_from_scenes(scenes)


def recalculate_durations_payload(payload: dict[str, Any]) -> dict[str, Any]:
    validated = validate_edited_preview_payload(payload)
    scenes = validated["scenes"]

    new_scenes = recalculate_scene_durations(scenes)
    validated["scenes"] = new_scenes
    validated["script_text"] = rebuild_script_text_from_scenes(new_scenes)

    return validated


def rebuild_subtitles_payload(payload: dict[str, Any]) -> dict[str, Any]:
    validated = validate_edited_preview_payload(payload)
    scenes = validated["scenes"]

    new_subtitles = rebuild_subtitles_from_scenes(scenes)
    validated["subtitle_segments"] = new_subtitles
    validated["script_text"] = rebuild_script_text_from_scenes(scenes)

    return validated


def recalculate_all_payload(payload: dict[str, Any]) -> dict[str, Any]:
    validated = validate_edited_preview_payload(payload)
    new_scenes = recalculate_scene_durations(validated["scenes"])
    new_subtitles = rebuild_subtitles_from_scenes(new_scenes)

    validated["scenes"] = new_scenes
    validated["subtitle_segments"] = new_subtitles
    validated["script_text"] = rebuild_script_text_from_scenes(new_scenes)

    return validated