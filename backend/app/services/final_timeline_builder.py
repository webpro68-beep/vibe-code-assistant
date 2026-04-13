from __future__ import annotations

from typing import Any


def build_final_timeline(
    *,
    scenes: list[Any],
    subtitle_segments: list[dict[str, Any]] | dict[str, Any] | None,
    merged_video_path: str,
) -> list[dict[str, Any]]:
    """
    Build timeline cuối để frontend/UI dùng lại.
    Đây là bản production-safe tối thiểu.
    """
    timeline: list[dict[str, Any]] = []

    current_start = 0.0
    normalized_subtitles = subtitle_segments if isinstance(subtitle_segments, list) else []

    for scene in scenes:
        duration = _scene_duration_sec(scene)
        start_sec = current_start
        end_sec = current_start + duration

        scene_subtitles = [
            seg
            for seg in normalized_subtitles
            if float(seg.get("start_sec", 0)) < end_sec
            and float(seg.get("end_sec", 0)) > start_sec
        ]

        timeline.append(
            {
                "scene_id": str(getattr(scene, "id", "")),
                "scene_index": int(getattr(scene, "scene_index", 0)),
                "title": getattr(scene, "title", None),
                "status": getattr(scene, "status", None),
                "start_sec": round(start_sec, 3),
                "end_sec": round(end_sec, 3),
                "duration_sec": round(duration, 3),
                "output_url": getattr(scene, "output_url", None),
                "output_path": getattr(scene, "output_path", None),
                "subtitles": scene_subtitles,
                "merged_video_path": merged_video_path,
            }
        )

        current_start = end_sec

    return timeline


def _scene_duration_sec(scene: Any) -> float:
    for field in ("target_duration_sec", "provider_target_duration_sec", "duration_sec"):
        value = getattr(scene, field, None)
        if value is not None:
            try:
                parsed = float(value)
                if parsed > 0:
                    return parsed
            except Exception:
                pass
    return 0.0