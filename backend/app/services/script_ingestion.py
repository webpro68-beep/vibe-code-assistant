from __future__ import annotations

import math
import re
from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document


ALLOWED_EXTENSIONS = {".txt", ".docx"}
MAX_SIZE_BYTES = 5 * 1024 * 1024


def validate_script_file(filename: str, content: bytes) -> str:
    if not filename:
        raise ValueError("Missing filename")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Only .txt and .docx are supported")

    if len(content) > MAX_SIZE_BYTES:
        raise ValueError("File too large")

    return ext


def parse_script_file_bytes(ext: str, content: bytes) -> str:
    ext = ext.lower()

    if ext == ".txt":
        return content.decode("utf-8", errors="ignore").strip()

    if ext == ".docx":
        doc = Document(BytesIO(content))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs).strip()

    return ""


def normalize_script_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    merged = "\n".join(lines)
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    return merged.strip()


def estimate_duration(text: str) -> float:
    words = len(text.split())
    duration = max(3.0, round(words / 2.6, 1))
    return min(duration, 25.0)


def split_script_into_scenes(script_text: str, max_scenes: int = 12) -> list[dict[str, Any]]:
    text = normalize_script_text(script_text)
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return []

    if len(paragraphs) <= max_scenes:
        return [
            {
                "scene_index": i + 1,
                "title": f"Scene {i + 1}",
                "script_text": paragraph,
                "target_duration_sec": estimate_duration(paragraph),
            }
            for i, paragraph in enumerate(paragraphs)
        ]

    chunk_size = math.ceil(len(paragraphs) / max_scenes)
    scenes: list[dict[str, Any]] = []

    for i in range(0, len(paragraphs), chunk_size):
        chunk = paragraphs[i : i + chunk_size]
        merged = " ".join(chunk).strip()
        scenes.append(
            {
                "scene_index": len(scenes) + 1,
                "title": f"Scene {len(scenes) + 1}",
                "script_text": merged,
                "target_duration_sec": estimate_duration(merged),
            }
        )

    return scenes[:max_scenes]


def chunk_words(text: str, words_per_chunk: int = 6) -> list[str]:
    words = text.split()
    if not words:
        return []
    return [
        " ".join(words[i : i + words_per_chunk])
        for i in range(0, len(words), words_per_chunk)
    ]


def build_subtitle_segments_from_scenes(
    scenes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    cursor = 0.0

    for scene in scenes:
        scene_text = (scene.get("script_text") or "").strip()
        if not scene_text:
            continue

        chunks = chunk_words(scene_text, words_per_chunk=6)
        if not chunks:
            continue

        scene_duration = float(scene.get("target_duration_sec", 5.0))
        segment_duration = max(0.6, round(scene_duration / len(chunks), 2))

        for chunk in chunks:
            start = round(cursor, 2)
            end = round(cursor + segment_duration, 2)
            segments.append(
                {
                    "scene_index": scene.get("scene_index"),
                    "text": chunk,
                    "start_sec": start,
                    "end_sec": end,
                }
            )
            cursor = end

    return segments


def build_preview_payload(
    *,
    filename: str | None,
    script_text: str,
    aspect_ratio: str,
    target_platform: str,
    style_preset: str | None,
) -> dict[str, Any]:
    normalized = normalize_script_text(script_text)
    if not normalized:
        raise ValueError("Parsed script is empty")

    scenes = split_script_into_scenes(normalized, max_scenes=12)
    subtitles = build_subtitle_segments_from_scenes(scenes)

    if not scenes:
        raise ValueError("Unable to generate scenes from script")

    return {
        "source_mode": "script_upload",
        "aspect_ratio": aspect_ratio,
        "target_platform": target_platform,
        "style_preset": style_preset,
        "original_filename": filename,
        "script_text": normalized,
        "scenes": scenes,
        "subtitle_segments": subtitles,
    }
	