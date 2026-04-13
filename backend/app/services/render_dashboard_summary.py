from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.render_incident_state import RenderIncidentState
from app.models.render_job import RenderJob
from app.models.render_timeline_event import RenderTimelineEvent

HEALTH_EVENTS = {
    'job_health_degraded', 'job_health_stalled', 'job_health_recovered', 'job_health_failed', 'job_health_completed', 'job_health_healthy', 'job_health_queued'
}


def _transition_summary(db: Session, window: timedelta, label: str) -> dict:
    since = datetime.utcnow() - window
    rows = db.query(RenderTimelineEvent).filter(RenderTimelineEvent.event_type.in_(list(HEALTH_EVENTS)), RenderTimelineEvent.occurred_at >= since).all()
    counts = {'degraded':0,'stalled':0,'recovered':0,'failed':0,'completed':0}
    for r in rows:
        for key in list(counts):
            if r.event_type == f'job_health_{key}':
                counts[key] += 1
    return {'window': label, 'total_transitions': len(rows), 'degraded_transitions': counts['degraded'], 'stalled_transitions': counts['stalled'], 'recovered_transitions': counts['recovered'], 'failed_transitions': counts['failed'], 'completed_transitions': counts['completed']}


def get_render_dashboard_summary(db: Session) -> dict:
    jobs = db.query(RenderJob).all()
    counts = {'healthy':0,'degraded':0,'stalled':0,'failed':0,'completed':0,'queued':0}
    by_provider = {}
    active = stalled = degraded = 0
    for j in jobs:
        hs = j.health_status or 'queued'
        counts[hs] = counts.get(hs,0) + 1
        active += j.active_scene_count or 0
        stalled += j.stalled_scene_count or 0
        degraded += j.degraded_scene_count or 0
        item = by_provider.setdefault(j.provider, {'provider': j.provider, 'total_jobs': 0, 'healthy_jobs':0, 'degraded_jobs':0, 'stalled_jobs':0, 'failed_jobs':0, 'completed_jobs':0})
        item['total_jobs'] += 1
        key = f'{hs}_jobs'
        if key in item:
            item[key] += 1
    return {
        'total_jobs': len(jobs),
        'healthy_jobs': counts.get('healthy',0),
        'degraded_jobs': counts.get('degraded',0),
        'stalled_jobs': counts.get('stalled',0),
        'failed_jobs': counts.get('failed',0),
        'completed_jobs': counts.get('completed',0),
        'queued_jobs': counts.get('queued',0),
        'total_active_scenes': active,
        'total_stalled_scenes': stalled,
        'total_degraded_scenes': degraded,
        'counts_by_provider': list(by_provider.values()),
        'recent_transitions': [_transition_summary(db, timedelta(hours=1), '1h'), _transition_summary(db, timedelta(hours=24), '24h')],
    }


def get_recent_incidents(db: Session, *, limit: int = 20, provider: str | None = None, show_muted: bool = False, workflow_status: str | None = None, assigned_to: str | None = None, segment: str | None = None) -> dict:
    q = db.query(RenderIncidentState).order_by(RenderIncidentState.status.asc(), RenderIncidentState.current_severity_rank.desc(), RenderIncidentState.last_seen_at.desc())
    if provider:
        q = q.filter(RenderIncidentState.provider == provider)
    if workflow_status:
        q = q.filter(RenderIncidentState.status == workflow_status)
    if assigned_to:
        q = q.filter(RenderIncidentState.assigned_to == assigned_to)
    if segment == "untriaged":
        q = q.filter(RenderIncidentState.acknowledged.is_(False), RenderIncidentState.assigned_to.is_(None), RenderIncidentState.resolved_at.is_(None))
    elif segment == "mine":
        if assigned_to:
            q = q.filter(RenderIncidentState.assigned_to == assigned_to)
    elif segment == "assigned":
        q = q.filter(RenderIncidentState.assigned_to.is_not(None), RenderIncidentState.resolved_at.is_(None))
    elif segment == "muted":
        q = q.filter(RenderIncidentState.muted.is_(True))
    elif segment == "resolved":
        q = q.filter(RenderIncidentState.resolved_at.is_not(None))
    elif segment == "active":
        q = q.filter(RenderIncidentState.resolved_at.is_(None))
    if not show_muted:
        q = q.filter(RenderIncidentState.suppressed.is_(False))
    states = q.limit(limit).all()
    items = []
    for state in states:
        job = db.query(RenderJob).filter(RenderJob.id == state.job_id).first()
        payload = {}
        items.append({
            'event_id': state.current_event_id or state.id,
            'incident_key': state.incident_key,
            'event_type': state.current_event_type or 'incident_open',
            'occurred_at': state.last_seen_at,
            'previous_status': None,
            'current_status': state.status,
            'previous_reason': None,
            'current_reason': state.suppression_reason or state.note,
            'workflow_status': state.status,
            'acknowledged': state.acknowledged,
            'muted': state.muted,
            'assigned_to': state.assigned_to,
            'job': {
                'job_id': state.job_id, 'project_id': state.project_id, 'provider': state.provider, 'status': job.status if job else 'unknown',
                'health_status': job.health_status if job else None, 'health_reason': job.health_reason if job else None,
                'planned_scene_count': job.planned_scene_count if job else 0, 'processing_scene_count': job.processing_scene_count if job else 0,
                'succeeded_scene_count': job.completed_scene_count if job else 0, 'failed_scene_count_snapshot': job.failed_scene_count_snapshot if job else 0,
                'stalled_scene_count': job.stalled_scene_count if job else 0, 'degraded_scene_count': job.degraded_scene_count if job else 0,
                'active_scene_count': job.active_scene_count if job else 0, 'created_at': job.created_at if job else None, 'updated_at': job.updated_at if job else None, 'last_event_at': job.last_event_at if job else None, 'last_health_transition_at': job.last_health_transition_at if job else None,
            },
            'payload': payload,
        })
    return {'items': items, 'limit': limit, 'total_returned': len(items), 'next_cursor': None}
