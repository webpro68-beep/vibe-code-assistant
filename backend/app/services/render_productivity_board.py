from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.render_incident_action import RenderIncidentAction
from app.models.render_incident_state import RenderIncidentState
from app.services.render_access_control import get_or_create_access_profile, list_access_profiles


ACTION_MAP = {
    "acknowledge": "acknowledged_count",
    "assign": "assigned_count",
    "mute": "muted_count",
    "resolve": "resolved_count",
    "reopen": "reopened_count",
    "note_updated": "note_updates",
}


def get_productivity_board(db: Session, *, actor: str, days: int = 7) -> dict:
    requester = get_or_create_access_profile(db, actor=actor)
    profiles = list_access_profiles(db, actor=actor, team_only=False)
    profile_by_actor = {p["actor_id"]: p for p in profiles}
    since = datetime.utcnow() - timedelta(days=days)

    rows = db.query(RenderIncidentAction).filter(RenderIncidentAction.created_at >= since).all()
    op = defaultdict(lambda: {
        "active_assigned": 0,
        "acknowledged_count": 0,
        "assigned_count": 0,
        "muted_count": 0,
        "resolved_count": 0,
        "reopened_count": 0,
        "note_updates": 0,
    })

    for row in rows:
        target = op[row.actor]
        field = ACTION_MAP.get(row.action_type)
        if field:
            target[field] += 1

    active_rows = db.query(RenderIncidentState).filter(RenderIncidentState.assigned_to.isnot(None), RenderIncidentState.resolved_at.is_(None)).all()
    for row in active_rows:
        op[row.assigned_to]["active_assigned"] += 1

    operator_items = []
    for actor_id, counters in op.items():
        profile = profile_by_actor.get(actor_id)
        if requester["role"] == "operator" and actor_id != actor:
            continue
        if requester["role"] == "team_lead" and profile and profile.get("team_id") != requester.get("team_id"):
            continue
        operator_items.append({
            "actor": actor_id,
            "role": profile.get("role") if profile else None,
            "team_id": profile.get("team_id") if profile else None,
            **counters,
        })
    operator_items.sort(key=lambda x: (-x["resolved_count"], -x["assigned_count"], x["actor"]))

    teams = defaultdict(lambda: {
        "member_count": 0,
        "active_assigned": 0,
        "acknowledged_count": 0,
        "assigned_count": 0,
        "muted_count": 0,
        "resolved_count": 0,
        "reopened_count": 0,
        "note_updates": 0,
    })
    for item in operator_items:
        team_id = item.get("team_id") or "unassigned"
        t = teams[team_id]
        t["member_count"] += 1
        for k in ["active_assigned", "acknowledged_count", "assigned_count", "muted_count", "resolved_count", "reopened_count", "note_updates"]:
            t[k] += int(item.get(k, 0))

    team_items = [{"team_id": team_id, **vals} for team_id, vals in teams.items()]
    team_items.sort(key=lambda x: (-x["resolved_count"], x["team_id"]))
    return {"days": days, "operators": operator_items, "teams": team_items}
