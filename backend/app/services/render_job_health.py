from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.render_job import RenderJob
from app.models.render_scene_task import RenderSceneTask
from app.models.render_timeline_event import RenderTimelineEvent
from app.services.render_timeline_writer import append_timeline_event
from app.services.render_incident_projector import project_timeline_event_to_incident_state

DEGRADED_CALLBACK_STALE_SECONDS = 180
DEGRADED_PROCESSING_AGE_SECONDS = 240


def _latest_event_time_for_job(db: Session, job_id: str):
    return db.query(func.max(RenderTimelineEvent.occurred_at)).filter(RenderTimelineEvent.job_id == job_id).scalar()


def build_render_job_health_summary(db: Session, job: RenderJob) -> dict:
    scenes = list(job.scenes or [])
    queued_scenes = [s for s in scenes if s.status in {'queued', 'submitted'}]
    processing_scenes = [s for s in scenes if s.status == 'processing']
    succeeded_scenes = [s for s in scenes if s.status == 'succeeded']
    failed_scenes = [s for s in scenes if s.status in {'failed', 'canceled'}]

    now = datetime.utcnow()
    stalled_scene_ids = []
    degraded_scene_ids = []
    reason = None

    for s in processing_scenes:
        if s.last_stalled_at is not None:
            stalled_scene_ids.append(s.id)
            continue
        if s.last_callback_at and (now - s.last_callback_at).total_seconds() >= DEGRADED_CALLBACK_STALE_SECONDS:
            degraded_scene_ids.append(s.id)
            reason = reason or 'callback_stale'
        elif s.started_at and (now - s.started_at).total_seconds() >= DEGRADED_PROCESSING_AGE_SECONDS:
            degraded_scene_ids.append(s.id)
            reason = reason or 'long_processing'

    if job.status == 'completed':
        health_status = 'completed'
    elif job.status == 'failed':
        health_status = 'failed'
    elif stalled_scene_ids:
        health_status = 'stalled'
        reason = reason or 'scene_processing_stalled'
    elif degraded_scene_ids or failed_scenes:
        health_status = 'degraded'
        reason = reason or ('scene_failed_partial' if failed_scenes else 'processing_degraded')
    elif processing_scenes:
        health_status = 'healthy'
    else:
        health_status = 'queued'

    last_event_at = _latest_event_time_for_job(db, job.id)
    if health_status == 'healthy' and last_event_at is not None:
        if (now - last_event_at).total_seconds() >= 180:
            health_status = 'degraded'
            reason = 'job_event_silence'

    return {
        'status': health_status,
        'reason': reason,
        'total_scenes': len(scenes),
        'queued_scenes': len(queued_scenes),
        'processing_scenes': len(processing_scenes),
        'succeeded_scenes': len(succeeded_scenes),
        'failed_scenes': len(failed_scenes),
        'stalled_scenes': len(stalled_scene_ids),
        'degraded_scenes': len(degraded_scene_ids),
        'last_event_at': last_event_at.isoformat() if last_event_at else None,
        'active_scene_ids': [s.id for s in processing_scenes],
        'stalled_scene_ids': stalled_scene_ids,
        'degraded_scene_ids': degraded_scene_ids,
    }


def refresh_render_job_health_snapshot(db: Session, job: RenderJob) -> dict:
    summary = build_render_job_health_summary(db, job)
    previous_status = job.health_status
    previous_reason = job.health_reason
    job.health_status = summary['status']
    job.health_reason = summary['reason']
    job.processing_scene_count = summary['processing_scenes']
    job.failed_scene_count_snapshot = summary['failed_scenes']
    job.stalled_scene_count = summary['stalled_scenes']
    job.degraded_scene_count = summary['degraded_scenes']
    job.active_scene_count = len(summary['active_scene_ids'])
    last_event_at = summary['last_event_at']
    job.last_event_at = datetime.fromisoformat(last_event_at) if last_event_at else job.last_event_at
    if summary['status'] != previous_status or summary['reason'] != previous_reason:
        job.last_health_transition_at = datetime.utcnow()
    db.commit()
    if summary['status'] != previous_status:
        event = append_timeline_event(
            db, job_id=job.id, scene_task_id=None, scene_index=None, source='system', event_type=f"job_health_{summary['status']}",
            occurred_at=datetime.utcnow(), status=job.status, provider=job.provider, payload={'previous_status': previous_status, 'current_status': summary['status'], 'previous_reason': previous_reason, 'current_reason': summary['reason']}
        )
        project_timeline_event_to_incident_state(db, event)
    return summary
