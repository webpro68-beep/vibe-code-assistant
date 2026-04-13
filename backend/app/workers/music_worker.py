from __future__ import annotations

import asyncio

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.audio.music_selection_service import generate_music_asset


@celery_app.task(name="audio.generate_music")
def generate_music_asset_task(music_asset_id: str) -> dict:
    db = SessionLocal()
    try:
        row = asyncio.run(generate_music_asset(db, music_asset_id))
        return {"ok": True, "music_asset_id": row.id, "public_url": row.public_url}
    finally:
        db.close()
