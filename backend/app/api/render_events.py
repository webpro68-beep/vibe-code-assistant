from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.render_events import RenderEventItem, RenderEventsResponse
from app.services.render_repository import get_render_job_by_id, list_timeline_events_for_job, list_timeline_events_for_scene

router = APIRouter(prefix='/api/v1/render', tags=['render-events'])


def _payload(v: str | None) -> dict:
    if not v:
        return {}
    try:
        return json.loads(v)
    except Exception:
        return {'raw': v}


@router.get('/jobs/{job_id}/events', response_model=RenderEventsResponse)
async def get_job_events(job_id: str, db: Session = Depends(get_db)):
    job = get_render_job_by_id(db, job_id, with_scenes=False)
    if not job:
        raise HTTPException(status_code=404, detail='Render job not found')
    items = list_timeline_events_for_job(db, job_id)
    return RenderEventsResponse(items=[RenderEventItem(id=e.id, source=e.source, event_type=e.event_type, job_id=e.job_id, scene_task_id=e.scene_task_id, scene_index=e.scene_index, provider=e.provider, status=e.status, provider_status_raw=e.provider_status_raw, failure_code=e.failure_code, failure_category=e.failure_category, error_message=e.error_message, provider_task_id=e.provider_task_id, provider_operation_name=e.provider_operation_name, provider_request_id=e.provider_request_id, signature_valid=e.signature_valid, processed=e.processed, occurred_at=e.occurred_at, payload=_payload(e.payload_json)) for e in items], total=len(items))


@router.get('/scenes/{scene_task_id}/events', response_model=RenderEventsResponse)
async def get_scene_events(scene_task_id: str, db: Session = Depends(get_db)):
    items = list_timeline_events_for_scene(db, scene_task_id)
    return RenderEventsResponse(items=[RenderEventItem(id=e.id, source=e.source, event_type=e.event_type, job_id=e.job_id, scene_task_id=e.scene_task_id, scene_index=e.scene_index, provider=e.provider, status=e.status, provider_status_raw=e.provider_status_raw, failure_code=e.failure_code, failure_category=e.failure_category, error_message=e.error_message, provider_task_id=e.provider_task_id, provider_operation_name=e.provider_operation_name, provider_request_id=e.provider_request_id, signature_valid=e.signature_valid, processed=e.processed, occurred_at=e.occurred_at, payload=_payload(e.payload_json)) for e in items], total=len(items))
