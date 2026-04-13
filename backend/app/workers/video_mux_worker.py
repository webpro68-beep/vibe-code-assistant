from __future__ import annotations

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.audio.audio_mux_service import mux_audio_to_video


@celery_app.task(name="audio.mux_video")
def mux_audio_to_video_task(audio_output_id: str) -> dict:
    db = SessionLocal()
    try:
        row = mux_audio_to_video(db, audio_output_id)
        return {"ok": True, "audio_output_id": row.id, "status": row.status, "final_muxed_video_url": row.final_muxed_video_url}
    finally:
        db.close()
