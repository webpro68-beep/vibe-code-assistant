from __future__ import annotations

from pathlib import Path

from app.schemas.storage import StoredObject
from app.services.storage_service import upload_video_asset


def build_scene_storage_key(job_id: str, scene_index: int, filename: str) -> str:
    return f"jobs/{job_id}/scenes/{scene_index:04d}/{filename}"


def build_final_storage_key(job_id: str, filename: str) -> str:
    return f"jobs/{job_id}/final/{filename}"


def upload_scene_video(job_id: str, scene_index: int, local_path: str) -> StoredObject:
    filename = Path(local_path).name
    key = build_scene_storage_key(job_id, scene_index, filename)
    return upload_video_asset(local_path, key)


def upload_final_video(job_id: str, local_path: str) -> StoredObject:
    filename = Path(local_path).name
    key = build_final_storage_key(job_id, filename)
    return upload_video_asset(local_path, key)