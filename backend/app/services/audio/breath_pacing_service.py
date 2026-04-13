from __future__ import annotations

import re


PAUSE_BY_PUNCT = {
    ",": 220,
    ";": 300,
    ":": 320,
    ".": 580,
    "?": 620,
    "!": 640,
}

BREATH_PRESET_MULTIPLIER = {
    "cinematic_slow": 1.25,
    "natural_conversational": 1.0,
    "explainer_clean": 0.9,
    "dramatic_documentary": 1.35,
}


def build_breath_paced_segments(script_text: str, preset: str = "cinematic_slow") -> list[dict]:
    multiplier = BREATH_PRESET_MULTIPLIER.get(preset, 1.0)
    normalized = re.sub(r"\s+", " ", script_text.strip())
    if not normalized:
        return []

    chunks = re.split(r"(?<=[\.!?])\s+|\n+", normalized)
    segments: list[dict] = []

    for idx, chunk in enumerate([c.strip() for c in chunks if c.strip()], start=1):
        pause = _estimate_pause_ms(chunk, multiplier)
        estimated_duration_ms = _estimate_duration_ms(chunk, multiplier)
        segments.append(
            {
                "segment_index": idx,
                "text": chunk,
                "pause_after_ms": pause,
                "estimated_duration_ms": estimated_duration_ms,
            }
        )
    return segments


def _estimate_pause_ms(text: str, multiplier: float) -> int:
    last = text[-1] if text else "."
    base = PAUSE_BY_PUNCT.get(last, 260)
    word_count = max(1, len(text.split()))
    if word_count > 18:
        base += 220
    elif word_count > 12:
        base += 120
    return int(base * multiplier)


def _estimate_duration_ms(text: str, multiplier: float) -> int:
    word_count = max(1, len(text.split()))
    base = word_count * 380
    if word_count > 18:
        base += 300
    return int(base * multiplier)
