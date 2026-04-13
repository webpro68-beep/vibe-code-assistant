import subprocess
from pathlib import Path
from typing import Sequence


def format_srt_ts(value: float) -> str:
    total_ms = int(round(value * 1000))
    hours = total_ms // 3600000
    total_ms %= 3600000
    minutes = total_ms // 60000
    total_ms %= 60000
    seconds = total_ms // 1000
    milliseconds = total_ms % 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def write_srt(segments: Sequence[dict], output_path: str) -> str:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, seg in enumerate(segments, start=1):
        lines += [str(i), f"{format_srt_ts(seg['start_sec'])} --> {format_srt_ts(seg['end_sec'])}", seg["text"], ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return str(out)


def burn_subtitles(video_path: str, srt_path: str, output_path: str) -> str:
    subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vf", f"subtitles={srt_path}", output_path], check=True)
    return output_path
