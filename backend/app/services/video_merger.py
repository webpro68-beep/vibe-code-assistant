import subprocess
from pathlib import Path
from typing import Sequence


def build_concat_file(paths: Sequence[str], workdir: Path) -> Path:
    concat_file = workdir / "concat.txt"
    concat_file.write_text("\n".join([f"file '{Path(p).as_posix()}'" for p in paths]), encoding="utf-8")
    return concat_file


def merge_clips_concat(paths: Sequence[str], output_path: str) -> str:
    workdir = Path(output_path).parent
    workdir.mkdir(parents=True, exist_ok=True)
    concat_file = build_concat_file(paths, workdir)
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", output_path], check=True)
    return output_path
