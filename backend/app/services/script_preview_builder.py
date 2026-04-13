from __future__ import annotations
import math

def build_preview_payload_from_text(
    script_text: str,
    aspect_ratio: str,
    target_platform: str,
    style_preset: str | None,
    source_mode: str = "script_upload",
) -> dict:
    text = (script_text or "").strip()
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()] or [text]
    scenes = []
    subtitle_segments = []
    cursor = 0.0
    for idx, para in enumerate(paragraphs, start=1):
        duration = max(4.0, min(8.0, round(len(para.split()) / 2.5, 1)))
        scenes.append({
            "scene_index": idx,
            "title": f"Scene {idx}",
            "script_text": para,
            "target_duration_sec": duration,
            "visual_prompt": para[:240],
        })
        subtitle_segments.append({
            "scene_index": idx,
            "text": para[:120],
            "start_sec": round(cursor, 2),
            "end_sec": round(cursor + duration, 2),
        })
        cursor += duration
    return {
        "source_mode": source_mode,
        "aspect_ratio": aspect_ratio,
        "target_platform": target_platform,
        "style_preset": style_preset,
        "script_text": text,
        "scenes": scenes,
        "subtitle_segments": subtitle_segments,
    }
