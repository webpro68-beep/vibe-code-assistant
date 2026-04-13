from __future__ import annotations

import subprocess
from pathlib import Path


def burn_subtitles_into_video(
    *,
    input_video_path: str,
    subtitle_file_path: str,
    output_video_path: str,
) -> None:
    """
    Burn subtitle SRT vào video bằng ffmpeg.
    """
    Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)

    subtitle_arg = subtitle_file_path.replace("\\", "/").replace(":", r"\:")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_video_path,
        "-vf",
        f"subtitles='{subtitle_arg}'",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        output_video_path,
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Subtitle burn failed\n"
            f"stdout={result.stdout}\n"
            f"stderr={result.stderr}"
        )