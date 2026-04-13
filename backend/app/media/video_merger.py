from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def normalize_clip(
    input_path: str,
    output_path: str,
    *,
    target_width: int = 1920,
    target_height: int = 1080,
    fps: int = 30,
) -> None:
    """
    Normalize tất cả clips về cùng profile trước concat.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-vf",
        f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,fps={fps}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        output_path,
    ]
    _run_ffmpeg(cmd)


def merge_clips_concat(
    clip_paths: list[str],
    output_path: str,
) -> None:
    """
    Concat sau khi tất cả clips đã normalize về cùng profile.
    """
    if not clip_paths:
        raise ValueError("clip_paths must not be empty")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    concat_list_path = output.parent / "concat_list.txt"
    concat_lines = []
    for clip in clip_paths:
        safe_path = Path(clip).resolve().as_posix().replace("'", r"'\''")
        concat_lines.append(f"file '{safe_path}'")

    concat_list_path.write_text("\n".join(concat_lines), encoding="utf-8")

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list_path),
        "-c",
        "copy",
        output_path,
    ]
    _run_ffmpeg(cmd)


def build_subtitle_file_from_segments(
    subtitle_segments: list[dict[str, Any]],
    output_srt_path: str,
) -> None:
    Path(output_srt_path).parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for idx, seg in enumerate(subtitle_segments, start=1):
        start_sec = float(seg.get("start_sec", 0))
        end_sec = float(seg.get("end_sec", 0))
        text = str(seg.get("text") or "").strip()

        if not text:
            continue

        lines.append(str(idx))
        lines.append(f"{_to_srt_ts(start_sec)} --> {_to_srt_ts(end_sec)}")
        lines.append(text)
        lines.append("")

    Path(output_srt_path).write_text("\n".join(lines), encoding="utf-8")


def extract_thumbnail(
    input_video_path: str,
    output_image_path: str,
    *,
    timestamp_seconds: float = 1.0,
) -> None:
    Path(output_image_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(timestamp_seconds),
        "-i",
        input_video_path,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        output_image_path,
    ]
    _run_ffmpeg(cmd)


def _to_srt_ts(total_seconds: float) -> str:
    millis = int(round(total_seconds * 1000))
    hours = millis // 3_600_000
    millis %= 3_600_000
    minutes = millis // 60_000
    millis %= 60_000
    seconds = millis // 1000
    millis %= 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "ffmpeg command failed\n"
            f"cmd={' '.join(cmd)}\n"
            f"stdout={result.stdout}\n"
            f"stderr={result.stderr}"
        )