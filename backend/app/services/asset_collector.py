from pathlib import Path
from app.core.config import settings

RENDER_CACHE_DIR = Path(settings.render_cache_dir)
RENDER_CACHE_DIR.mkdir(parents=True, exist_ok=True)

async def cache_remote_video(job_id: str, scene_index: int, url: str) -> str:
    local_path = RENDER_CACHE_DIR / job_id / f"scene_{scene_index:03d}.mp4"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(b"")
    return str(local_path)
