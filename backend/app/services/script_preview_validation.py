from __future__ import annotations

from typing import Any


def validate_scene_sequence(scenes: list[dict[str, Any]]) -> None:
    expected = 1
    for scene in scenes:
        if int(scene.get("scene_index", 0)) != expected:
            raise ValueError("Scene indexes must be sequential starting from 1")
        expected += 1


def validate_scene_references_in_subtitles(
    scenes: list[dict[str, Any]],
    subtitles: list[dict[str, Any]],
) -> None:
    valid_indexes = {int(scene["scene_index"]) for scene in scenes}
    for seg in subtitles:
        scene_index = seg.get("scene_index")
        if scene_index is not None and int(scene_index) not in valid_indexes:
            raise ValueError(f"Invalid subtitle scene_index: {scene_index}")


def validate_subtitle_timeline(subtitles: list[dict[str, Any]]) -> None:
    prev_end = -1.0

    for seg in subtitles:
        start = float(seg["start_sec"])
        end = float(seg["end_sec"])

        if end <= start:
            raise ValueError("Subtitle end_sec must be greater than start_sec")

        if start < prev_end:
            raise ValueError("Subtitle timeline overlaps or is out of order")

        prev_end = end


def rebuild_script_text_from_scenes(scenes: list[dict[str, Any]]) -> str:
    chunks = [(scene.get("script_text") or "").strip() for scene in scenes]
    chunks = [chunk for chunk in chunks if chunk]
    if not chunks:
        raise ValueError("Unable to rebuild script_text from scenes")
    return "\n\n".join(chunks).strip()


def validate_edited_preview_payload(payload: dict[str, Any]) -> dict[str, Any]:
    scenes = payload.get("scenes") or []
    subtitles = payload.get("subtitle_segments") or []

    if not scenes:
        raise ValueError("At least one scene is required")

    if not subtitles:
        raise ValueError("At least one subtitle segment is required")

    validate_scene_sequence(scenes)
    validate_scene_references_in_subtitles(scenes, subtitles)
    validate_subtitle_timeline(subtitles)

    payload["script_text"] = rebuild_script_text_from_scenes(scenes)
    return payload