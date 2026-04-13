from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.render_incident_action import RenderIncidentAction
from app.models.render_incident_state import RenderIncidentState
from app.models.render_timeline_event import RenderTimelineEvent


def _payload(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except Exception:
        return {"raw": raw}


def serialize_incident_state(state: RenderIncidentState) -> dict[str, Any]:
    return {
        "incident_key": state.incident_key,
        "job_id": state.job_id,
        "project_id": state.project_id,
        "provider": state.provider,
        "incident_family": state.incident_family,
        "current_event_id": state.current_event_id,
        "current_event_type": state.current_event_type,
        "current_severity_rank": state.current_severity_rank,
        "first_seen_at": state.first_seen_at,
        "last_seen_at": state.last_seen_at,
        "last_transition_at": state.last_transition_at,
        "status": state.status,
        "acknowledged": state.acknowledged,
        "acknowledged_by": state.acknowledged_by,
        "acknowledged_at": state.acknowledged_at,
        "assigned_to": state.assigned_to,
        "assigned_by": state.assigned_by,
        "assigned_at": state.assigned_at,
        "muted": state.muted,
        "muted_until": state.muted_until,
        "muted_by": state.muted_by,
        "mute_reason": state.mute_reason,
        "suppressed": state.suppressed,
        "suppression_reason": state.suppression_reason,
        "reopen_count": state.reopen_count,
        "last_reopened_at": state.last_reopened_at,
        "resolved_at": state.resolved_at,
        "note": state.note,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }


def _serialize_timeline_row(row: RenderTimelineEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "source": row.source,
        "event_type": row.event_type,
        "job_id": row.job_id,
        "scene_task_id": row.scene_task_id,
        "scene_index": row.scene_index,
        "provider": row.provider,
        "status": row.status,
        "provider_status_raw": row.provider_status_raw,
        "failure_code": row.failure_code,
        "failure_category": row.failure_category,
        "error_message": row.error_message,
        "provider_task_id": row.provider_task_id,
        "provider_operation_name": row.provider_operation_name,
        "provider_request_id": row.provider_request_id,
        "occurred_at": row.occurred_at,
        "payload": _payload(row.payload_json),
    }


def list_incident_actions(db: Session, incident_key: str, *, limit: int = 100) -> list[dict[str, Any]]:
    rows = (
        db.query(RenderIncidentAction)
        .filter(RenderIncidentAction.incident_key == incident_key)
        .order_by(RenderIncidentAction.created_at.desc(), RenderIncidentAction.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "incident_key": row.incident_key,
            "event_id": row.event_id,
            "job_id": row.job_id,
            "action_type": row.action_type,
            "actor": row.actor,
            "reason": row.reason,
            "payload": _payload(row.payload_json),
            "created_at": row.created_at,
        }
        for row in rows
    ]


def list_incident_timeline_events(db: Session, state: RenderIncidentState, *, limit: int = 50) -> list[dict[str, Any]]:
    since = state.first_seen_at - timedelta(hours=2)
    until = state.last_seen_at + timedelta(hours=2)
    rows = (
        db.query(RenderTimelineEvent)
        .filter(RenderTimelineEvent.job_id == state.job_id)
        .filter(RenderTimelineEvent.occurred_at >= since)
        .filter(RenderTimelineEvent.occurred_at <= until)
        .order_by(RenderTimelineEvent.occurred_at.desc(), RenderTimelineEvent.id.desc())
        .limit(limit)
        .all()
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        if row.event_type.startswith("job_health_") or row.event_type.startswith("scene_") or row.id == state.current_event_id:
            items.append(_serialize_timeline_row(row))
    return items


def build_incident_projected_timeline(
    db: Session,
    state: RenderIncidentState,
    *,
    event_limit: int = 50,
    action_limit: int = 100,
) -> list[dict[str, Any]]:
    since = state.first_seen_at - timedelta(hours=4)
    until = max(state.last_seen_at, state.updated_at) + timedelta(hours=4)
    family_suffix = state.incident_family.removeprefix("health_")
    related_health_events = {state.current_event_type} if state.current_event_type else set()
    if family_suffix == "failed":
        related_health_events.update({"job_health_failed", "job_health_stalled", "job_health_degraded", "job_health_recovered", "job_health_completed"})
    elif family_suffix == "stalled":
        related_health_events.update({"job_health_stalled", "job_health_degraded", "job_health_recovered", "job_health_completed"})
    elif family_suffix == "degraded":
        related_health_events.update({"job_health_degraded", "job_health_recovered", "job_health_completed"})
    else:
        related_health_events.update({"job_health_recovered", "job_health_completed", "job_health_healthy", "job_health_queued"})

    timeline_rows = (
        db.query(RenderTimelineEvent)
        .filter(RenderTimelineEvent.job_id == state.job_id)
        .filter(RenderTimelineEvent.occurred_at >= since)
        .filter(RenderTimelineEvent.occurred_at <= until)
        .order_by(RenderTimelineEvent.occurred_at.desc(), RenderTimelineEvent.id.desc())
        .limit(event_limit)
        .all()
    )

    projected: list[dict[str, Any]] = []
    for row in timeline_rows:
        if row.id == state.current_event_id or row.event_type in related_health_events:
            projected.append(_serialize_timeline_row(row))

    action_rows = (
        db.query(RenderIncidentAction)
        .filter(RenderIncidentAction.incident_key == state.incident_key)
        .order_by(RenderIncidentAction.created_at.desc(), RenderIncidentAction.id.desc())
        .limit(action_limit)
        .all()
    )
    for row in action_rows:
        projected.append(
            {
                "id": f"proj_{row.id}",
                "source": "incident_action",
                "event_type": f"incident_{row.action_type}",
                "job_id": row.job_id,
                "scene_task_id": None,
                "scene_index": None,
                "provider": state.provider,
                "status": state.status,
                "provider_status_raw": None,
                "failure_code": None,
                "failure_category": None,
                "error_message": None,
                "provider_task_id": None,
                "provider_operation_name": None,
                "provider_request_id": None,
                "occurred_at": row.created_at,
                "payload": {
                    **_payload(row.payload_json),
                    "actor": row.actor,
                    "reason": row.reason,
                    "action_type": row.action_type,
                },
            }
        )

    projected.sort(key=lambda item: (item["occurred_at"], item["id"]), reverse=True)
    return projected[: max(event_limit, action_limit)]


def get_incident_history(db: Session, incident_key: str, *, action_limit: int = 100, event_limit: int = 50) -> dict[str, Any] | None:
    state = db.query(RenderIncidentState).filter(RenderIncidentState.incident_key == incident_key).first()
    if state is None:
        return None
    return {
        "incident": serialize_incident_state(state),
        "actions": list_incident_actions(db, incident_key, limit=action_limit),
        "timeline_events": list_incident_timeline_events(db, state, limit=event_limit),
        "projected_timeline": build_incident_projected_timeline(db, state, event_limit=event_limit, action_limit=action_limit),
    }


def update_incident_note(db: Session, *, incident_key: str, actor: str, note: str | None) -> RenderIncidentState | None:
    state = db.query(RenderIncidentState).filter(RenderIncidentState.incident_key == incident_key).first()
    if state is None:
        return None
    normalized = (note or "").strip() or None
    state.note = normalized
    state.updated_at = datetime.utcnow()
    db.add(
        RenderIncidentAction(
            id=f"ria_{uuid.uuid4().hex[:24]}",
            incident_key=incident_key,
            event_id=state.current_event_id,
            job_id=state.job_id,
            action_type="note_updated",
            actor=actor,
            reason=normalized,
            payload_json=json.dumps({"note": normalized}, ensure_ascii=False),
        )
    )
    db.commit()
    db.refresh(state)
    return state
