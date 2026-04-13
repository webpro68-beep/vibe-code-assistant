from __future__ import annotations

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.audio.audio_mix_service import mix_audio_tracks


@celery_app.task(name="audio.mix_tracks")
def mix_audio_tracks_task(audio_output_id: str) -> dict:
    db = SessionLocal()
    try:
        row = mix_audio_tracks(db, audio_output_id)
        return {"ok": True, "audio_output_id": row.id, "status": row.status, "mixed_audio_url": row.mixed_audio_url}
    finally:
        db.close()
