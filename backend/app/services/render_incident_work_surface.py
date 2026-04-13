from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session

from app.models.render_incident_state import RenderIncidentState

SEGMENTS = ["active", "untriaged", "assigned", "muted", "resolved", "mine"]


def _base_query(db: Session, provider: str | None = None, show_muted: bool = False):
    q = db.query(RenderIncidentState)
    if provider:
        q = q.filter(RenderIncidentState.provider == provider)
    if not show_muted:
        q = q.filter(RenderIncidentState.suppressed.is_(False))
    return q


def _segment_filter(q, segment: str, assignee: str | None = None):
    if segment == "untriaged":
        return q.filter(RenderIncidentState.acknowledged.is_(False), RenderIncidentState.assigned_to.is_(None), RenderIncidentState.resolved_at.is_(None))
    if segment == "mine" and assignee:
        return q.filter(RenderIncidentState.assigned_to == assignee)
    if segment == "assigned":
        return q.filter(RenderIncidentState.assigned_to.is_not(None), RenderIncidentState.resolved_at.is_(None))
    if segment == "muted":
        return q.filter(RenderIncidentState.muted.is_(True))
    if segment == "resolved":
        return q.filter(RenderIncidentState.resolved_at.is_not(None))
    return q.filter(RenderIncidentState.resolved_at.is_(None))


def get_incident_segment_metrics(db: Session, *, provider: str | None = None, show_muted: bool = False, assignee: str | None = None) -> dict:
    items = []
    now = datetime.utcnow()
    for segment in SEGMENTS:
        q = _segment_filter(_base_query(db, provider=provider, show_muted=show_muted), segment, assignee=assignee)
        rows = q.all()
        items.append({
            "segment": segment,
            "total": len(rows),
            "unacknowledged": sum(1 for r in rows if not r.acknowledged),
            "assigned": sum(1 for r in rows if bool(r.assigned_to)),
            "muted": sum(1 for r in rows if r.muted),
            "resolved": sum(1 for r in rows if r.resolved_at is not None),
            "stale_over_30m": sum(1 for r in rows if (now - r.last_seen_at).total_seconds() >= 1800),
            "high_severity": sum(1 for r in rows if (r.current_severity_rank or 0) >= 20),
        })
    return {"generated_at": now, "provider": provider, "show_muted": show_muted, "items": items}


def preview_bulk_action(db: Session, *, action_type: str, incident_keys: list[str], assigned_to: str | None = None, muted_until: datetime | None = None) -> dict:
    rows = db.query(RenderIncidentState).filter(RenderIncidentState.incident_key.in_(incident_keys)).all()
    by_key = {r.incident_key: r for r in rows}
    items = []
    eligible = 0
    for incident_key in incident_keys:
        row = by_key.get(incident_key)
        if not row:
            items.append({"incident_key": incident_key, "eligible": False, "reason": "incident_not_found"})
            continue
        reason = None
        is_eligible = True
        predicted_status = row.status
        predicted_assigned_to = row.assigned_to
        predicted_muted_until = row.muted_until
        if action_type == "acknowledge":
            if row.acknowledged:
                is_eligible = False
                reason = "already_acknowledged"
            else:
                predicted_status = "acknowledged"
        elif action_type == "assign":
            if not assigned_to:
                is_eligible = False
                reason = "missing_assigned_to"
            elif row.assigned_to == assigned_to and row.status == "assigned":
                is_eligible = False
                reason = "already_assigned_to_target"
            else:
                predicted_status = "assigned"
                predicted_assigned_to = assigned_to
        elif action_type == "mute":
            if row.muted and row.muted_until and muted_until and row.muted_until >= muted_until:
                is_eligible = False
                reason = "already_muted_longer"
            else:
                predicted_status = "muted"
                predicted_muted_until = muted_until
        elif action_type == "resolve":
            if row.resolved_at is not None or row.status == "resolved":
                is_eligible = False
                reason = "already_resolved"
            else:
                predicted_status = "resolved"
        if is_eligible:
            eligible += 1
        items.append({
            "incident_key": incident_key,
            "current_status": row.status,
            "assigned_to": row.assigned_to,
            "muted": row.muted,
            "acknowledged": row.acknowledged,
            "eligible": is_eligible,
            "reason": reason,
            "predicted_status": predicted_status,
            "predicted_assigned_to": predicted_assigned_to,
            "predicted_muted_until": predicted_muted_until,
        })
    return {"ok": True, "action_type": action_type, "attempted": len(incident_keys), "eligible": eligible, "skipped": len(incident_keys)-eligible, "items": items}
