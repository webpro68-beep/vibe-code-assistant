from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.render_incident_action import RenderIncidentAction
from app.models.render_incident_state import RenderIncidentState
from app.models.render_job import RenderJob
from app.models.render_timeline_event import RenderTimelineEvent

INCIDENT_SEVERITY_RANK = {
    "job_health_degraded": 10,
    "job_health_stalled": 20,
    "job_health_failed": 30,
    "job_health_recovered": 0,
    "job_health_completed": 0,
    "job_health_healthy": 0,
    "job_health_queued": 0,
}
RESOLVED_EVENT_TYPES = {"job_health_recovered", "job_health_completed", "job_health_healthy"}
ACTIVE_EVENT_TYPES = {"job_health_degraded", "job_health_stalled", "job_health_failed", "job_health_queued"}


def _family(event_type: str) -> str:
    return event_type.removeprefix("job_")


def _incident_key(job_id: str, event_type: str) -> str:
    return f"{job_id}:{_family(event_type)}"


def project_timeline_event_to_incident_state(db: Session, event: RenderTimelineEvent) -> RenderIncidentState | None:
    if not event.event_type.startswith("job_health_"):
        return None
    job = db.query(RenderJob).filter(RenderJob.id == event.job_id).first()
    if not job:
        return None

    key = _incident_key(event.job_id, event.event_type)
    state = db.query(RenderIncidentState).filter(RenderIncidentState.incident_key == key).first()
    now = event.occurred_at
    severity = INCIDENT_SEVERITY_RANK.get(event.event_type, 0)

    if state is None:
        state = RenderIncidentState(
            id=f"ris_{uuid.uuid4().hex[:24]}",
            incident_key=key,
            job_id=job.id,
            project_id=job.project_id,
            provider=job.provider,
            incident_family=_family(event.event_type),
            current_event_id=event.id,
            current_event_type=event.event_type,
            current_severity_rank=severity,
            first_seen_at=now,
            last_seen_at=now,
            last_transition_at=now,
            status="resolved" if event.event_type in RESOLVED_EVENT_TYPES else "open",
            suppressed=event.event_type in RESOLVED_EVENT_TYPES,
            suppression_reason="resolved" if event.event_type in RESOLVED_EVENT_TYPES else None,
            resolved_at=now if event.event_type in RESOLVED_EVENT_TYPES else None,
        )
        db.add(state)
    else:
        previously_resolved = state.status == "resolved"
        state.current_event_id = event.id
        state.current_event_type = event.event_type
        state.current_severity_rank = severity
        state.last_seen_at = now
        state.last_transition_at = now

        if event.event_type in RESOLVED_EVENT_TYPES:
            state.status = "resolved"
            state.suppressed = True
            state.suppression_reason = "resolved"
            state.resolved_at = now
        elif state.muted and state.muted_until and state.muted_until > now:
            state.status = "muted"
            state.suppressed = True
            state.suppression_reason = "muted_active"
        else:
            state.status = "open"
            state.suppressed = False
            state.suppression_reason = None
            state.resolved_at = None
            if previously_resolved:
                state.reopen_count += 1
                state.last_reopened_at = now

    db.commit()
    db.refresh(state)
    return state


def apply_incident_action(
    db: Session,
    *,
    incident_key: str,
    action_type: str,
    actor: str,
    reason: str | None = None,
    payload: dict | None = None,
) -> RenderIncidentState | None:
    state = db.query(RenderIncidentState).filter(RenderIncidentState.incident_key == incident_key).first()
    if state is None:
        return None

    now = datetime.utcnow()
    payload = payload or {}

    if action_type == "acknowledge":
        state.acknowledged = True
        state.acknowledged_by = actor
        state.acknowledged_at = now
        if state.status not in {"resolved", "muted"}:
            state.status = "acknowledged"
    elif action_type == "assign":
        state.assigned_to = payload.get("assigned_to")
        state.assigned_by = actor
        state.assigned_at = now
        if state.status not in {"resolved", "muted"}:
            state.status = "assigned"
    elif action_type == "mute":
        state.muted = True
        state.muted_by = actor
        state.muted_until = payload.get("muted_until")
        state.mute_reason = reason
        state.suppressed = True
        state.suppression_reason = "muted_active"
        state.status = "muted"
    elif action_type == "resolve":
        state.status = "resolved"
        state.resolved_at = now
        state.suppressed = True
        state.suppression_reason = "resolved"
    elif action_type in {"reopen", "unresolve"}:
        state.status = "open"
        state.suppressed = False
        state.suppression_reason = None
        state.resolved_at = None
        state.muted = False
        state.muted_until = None
        state.reopen_count += 1
        state.last_reopened_at = now

    if reason and action_type != "note_updated":
        state.note = reason
    state.last_transition_at = now

    db.add(
        RenderIncidentAction(
            id=f"ria_{uuid.uuid4().hex[:24]}",
            incident_key=incident_key,
            event_id=state.current_event_id,
            job_id=state.job_id,
            action_type=action_type,
            actor=actor,
            reason=reason,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
    )
    db.commit()
    db.refresh(state)
    return state
