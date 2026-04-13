from __future__ import annotations

import asyncio

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.voice_profile import VoiceProfile
from app.services.audio.voice_clone_service import clone_voice_if_needed


@celery_app.task(name="audio.clone_voice_profile")
def clone_voice_profile_task(voice_profile_id: str) -> dict:
    db = SessionLocal()
    try:
        row = db.query(VoiceProfile).filter(VoiceProfile.id == voice_profile_id).first()
        if row is None:
            return {"ok": False, "error": "voice_profile_not_found"}
        updated = asyncio.run(clone_voice_if_needed(db, row))
        return {"ok": True, "voice_profile_id": updated.id, "provider_voice_id": updated.provider_voice_id}
    finally:
        db.close()
