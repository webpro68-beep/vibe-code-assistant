from __future__ import annotations
from sqlalchemy.orm import Session
from app.services.render_repository import get_render_job_by_id, list_timeline_events_for_job

def build_project_render_event_summary(db: Session, job_id: str) -> list[dict]:
    job = get_render_job_by_id(db, job_id, with_scenes=False)
    if not job:
        return []
    items = list_timeline_events_for_job(db, job_id)
    return [{"id": e.id, "event_type": e.event_type, "status": e.status, "scene_index": e.scene_index, "error_message": e.error_message, "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None} for e in items]
