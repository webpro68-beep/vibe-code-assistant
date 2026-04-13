from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.render_repository import (
    get_render_job_by_id,
    get_scene_task_by_id,
)
from app.services.signed_url_service import generate_download_signed_url

router = APIRouter(prefix="/api/v1/storage", tags=["storage"])


def _build_filename_from_key(storage_key: str | None, fallback: str) -> str:
    if not storage_key:
        return fallback
    return Path(storage_key).name or fallback


def _safe_generate_signed_url(
    *,
    key: str,
    filename: str,
) -> str:
    try:
        return generate_download_signed_url(
            key=key,
            filename=filename,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate signed URL: {exc}",
        ) from exc


@router.get("/jobs/{job_id}/final-download")
async def get_final_video_download_url(
    job_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Trả signed download URL cho final video của render job.
    """
    job = get_render_job_by_id(db, job_id, with_scenes=False)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Render job not found",
        )

    storage_key = getattr(job, "final_storage_key", None)
    storage_bucket = getattr(job, "final_storage_bucket", None)

    if not storage_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Final video storage key not found",
        )

    filename = _build_filename_from_key(
        storage_key,
        fallback=f"{job.id}.mp4",
    )
    signed_url = _safe_generate_signed_url(
        key=storage_key,
        filename=filename,
    )

    return {
        "job_id": job.id,
        "bucket": storage_bucket,
        "key": storage_key,
        "signed_url": signed_url,
        "filename": filename,
    }


@router.get("/scenes/{scene_task_id}/download")
async def get_scene_video_download_url(
    scene_task_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Trả signed download URL cho scene asset đã upload lên object storage.
    """
    scene = get_scene_task_by_id(db, scene_task_id)
    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene task not found",
        )

    storage_key = getattr(scene, "storage_key", None)
    storage_bucket = getattr(scene, "storage_bucket", None)

    if not storage_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene storage key not found",
        )

    fallback_name = f"scene_{scene.scene_index}.mp4"
    filename = _build_filename_from_key(storage_key, fallback=fallback_name)
    signed_url = _safe_generate_signed_url(
        key=storage_key,
        filename=filename,
    )

    return {
        "scene_task_id": scene.id,
        "job_id": scene.job_id,
        "scene_index": scene.scene_index,
        "bucket": storage_bucket,
        "key": storage_key,
        "signed_url": signed_url,
        "filename": filename,
    }