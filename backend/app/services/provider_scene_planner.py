from __future__ import annotations

import math
from typing import Any

from app.services.render_provider_registry import get_provider_capabilities


def estimate_duration_from_text(text: str) -> float:
    words = len((text or "").split())
    duration = max(3.0, round(words / 2.6, 1))
    return duration


def split_text_into_chunks(text: str, chunks: int) -> list[str]:
    words = text.split()
    if not words or chunks <= 1:
        return [text.strip()] if text.strip() else []

    chunk_size = math.ceil(len(words) / chunks)
    out: list[str] = []

    for i in range(0, len(words), chunk_size):
        out.append(" ".join(words[i:i + chunk_size]).strip())

    return [x for x in out if x]


def plan_provider_scenes(
    scenes: list[dict[str, Any]],
    provider: str,
) -> list[dict[str, Any]]:
    caps = get_provider_capabilities(provider)
    planned: list[dict[str, Any]] = []

    for scene in scenes:
        text = (scene.get("script_text") or "").strip()
        title = (scene.get("title") or "Scene").strip()

        if not text:
            continue

        estimated = estimate_duration_from_text(text)

        if estimated <= caps.max_scene_duration_sec:
            planned.append({
                **scene,
                "provider": provider,
                "provider_mode": caps.recommended_mode,
                "provider_target_duration_sec": min(
                    max(estimated, 3.0),
                    caps.max_scene_duration_sec,
                ),
            })
            continue

        chunk_count = math.ceil(estimated / caps.max_scene_duration_sec)
        chunks = split_text_into_chunks(text, chunk_count)

        for idx, chunk in enumerate(chunks, start=1):
            planned.append({
                "scene_index": len(planned) + 1,
                "title": f"{title} — Part {idx}",
                "script_text": chunk,
                "target_duration_sec": estimate_duration_from_text(chunk),
                "provider": provider,
                "provider_mode": caps.recommended_mode,
                "provider_target_duration_sec": min(
                    max(estimate_duration_from_text(chunk), 3.0),
                    caps.max_scene_duration_sec,
                ),
                "source_scene_index": scene.get("scene_index"),
            })

    return planned