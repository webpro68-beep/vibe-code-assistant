from __future__ import annotations

import asyncio

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.audio.narration_service import run_narration_job


@celery_app.task(name="audio.run_narration")
def run_narration_job_task(narration_job_id: str) -> dict:
    db = SessionLocal()
    try:
        row = asyncio.run(run_narration_job(db, narration_job_id))
        return {"ok": True, "narration_job_id": row.id, "status": row.status, "output_url": row.output_url}
    finally:
        db.close()
