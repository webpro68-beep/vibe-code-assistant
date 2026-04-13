from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.render_incident_saved_view import RenderIncidentSavedView
from app.models.render_incident_state import RenderIncidentState
from app.models.render_operator_access_profile import RenderOperatorAccessProfile
from app.services.render_access_control import get_or_create_access_profile, list_access_profiles
from app.services.render_incident_saved_views import _can_view, _load_roles, serialize_saved_view
from app.services.render_productivity_board import get_productivity_board
from app.models.render_incident_action import RenderIncidentAction


def get_saved_view_effective_access_preview(db: Session, *, view_id: str, actor: str) -> dict[str, Any] | None:
    row = db.query(RenderIncidentSavedView).filter(RenderIncidentSavedView.id == view_id).first()
    if not row:
        return None
    requester = get_or_create_access_profile(db, actor=actor)
    profiles = list_access_profiles(db, actor=actor, team_only=False)
    entries = []
    visible_to_count = 0
    for profile in profiles:
        can_view = _can_view(row, profile)
        reason = None
        if can_view:
            if row.owner_actor == profile['actor_id']:
                reason = 'owner'
            elif row.share_scope == 'shared_all' or row.is_shared:
                reason = 'shared_all'
            elif row.share_scope == 'team' and row.shared_team_id == profile.get('team_id'):
                reason = 'team_scope'
            elif row.share_scope == 'role' and profile.get('role') in _load_roles(row.allowed_roles_json):
                reason = 'role_scope'
        else:
            if row.share_scope == 'team':
                reason = 'outside_team_scope'
            elif row.share_scope == 'role':
                reason = 'outside_role_scope'
            else:
                reason = 'private'
        if can_view:
            visible_to_count += 1
        entries.append({
            'actor_id': profile['actor_id'],
            'role': profile.get('role'),
            'team_id': profile.get('team_id'),
            'can_view': can_view,
            'reason': reason,
        })
    view = serialize_saved_view(row)
    return {
        'view_id': row.id,
        'view_name': row.name,
        'requester_actor': actor,
        'requester_role': requester.get('role'),
        'requester_team_id': requester.get('team_id'),
        'share_scope': row.share_scope,
        'owner_actor': row.owner_actor,
        'shared_team_id': row.shared_team_id,
        'allowed_roles': view.get('allowed_roles', []),
        'visible_to_count': visible_to_count,
        'entries': entries,
    }


def _default_bulk_policy(role: str) -> dict[str, Any]:
    base = {
        'viewer': {'max_bulk_items': 0, 'max_high_severity_items': 0},
        'operator': {'max_bulk_items': 25, 'max_high_severity_items': 5},
        'team_lead': {'max_bulk_items': 100, 'max_high_severity_items': 20},
        'admin': {'max_bulk_items': 200, 'max_high_severity_items': 100},
    }
    return dict(base.get(role, base['operator']))


def evaluate_bulk_guardrails(db: Session, *, actor: str, action_type: str, incident_keys: list[str]) -> dict[str, Any]:
    profile = get_or_create_access_profile(db, actor=actor)
    policy = _default_bulk_policy(profile.get('role', 'operator'))
    policy.update({k: v for k, v in (profile.get('scopes') or {}).items() if k in {'max_bulk_items', 'max_high_severity_items'}})
    rows = db.query(RenderIncidentState).filter(RenderIncidentState.incident_key.in_(incident_keys)).all()
    high_severity = sum(1 for r in rows if (r.current_severity_rank or 0) >= 20)
    unresolved = sum(1 for r in rows if r.resolved_at is None)
    assigned_to = sorted({r.assigned_to for r in rows if r.assigned_to})
    blocked_reasons: list[str] = []
    warnings: list[str] = []
    if len(incident_keys) > int(policy.get('max_bulk_items', 25)):
        blocked_reasons.append(f"selection_exceeds_max_bulk_items:{len(incident_keys)}>{policy.get('max_bulk_items')}")
    if action_type in {'assign', 'mute', 'resolve'} and high_severity > int(policy.get('max_high_severity_items', 5)):
        blocked_reasons.append(f"high_severity_exceeds_limit:{high_severity}>{policy.get('max_high_severity_items')}")
    if profile.get('role') == 'operator' and any(a and a != actor for a in assigned_to):
        blocked_reasons.append('operator_cannot_bulk_mutate_other_assignees')
    if unresolved == 0:
        warnings.append('selection_contains_only_resolved_items')
    if high_severity:
        warnings.append(f'high_severity_items:{high_severity}')
    return {
        'ok': not blocked_reasons,
        'action_type': action_type,
        'actor': actor,
        'actor_role': profile.get('role'),
        'actor_team_id': profile.get('team_id'),
        'policy': policy,
        'observed': {
            'selection_size': len(incident_keys),
            'matched_items': len(rows),
            'high_severity_items': high_severity,
            'unresolved_items': unresolved,
            'assignee_pool': assigned_to,
        },
        'blocked_reasons': blocked_reasons,
        'warnings': warnings,
    }


def get_productivity_trend_windows(db: Session, *, actor: str, windows: list[int]) -> dict[str, Any]:
    normalized = sorted({max(1, min(int(w), 30)) for w in windows})
    requester = get_or_create_access_profile(db, actor=actor)
    max_days = max(normalized) if normalized else 7
    window_items = []
    for days in normalized:
        board = get_productivity_board(db, actor=actor, days=days)
        window_items.append({
            'days': days,
            'team_totals': board.get('teams', []),
            'operator_totals': board.get('operators', []),
        })

    since = datetime.utcnow() - timedelta(days=max_days)
    actions = db.query(RenderIncidentAction).filter(RenderIncidentAction.created_at >= since).all()
    actor_to_team = {p.actor_id: p.team_id for p in db.query(RenderOperatorAccessProfile).all()}
    daily = defaultdict(lambda: {'resolved_count': 0, 'assigned_count': 0, 'acknowledged_count': 0, 'muted_count': 0})
    action_map = {
        'resolve': 'resolved_count',
        'assign': 'assigned_count',
        'acknowledge': 'acknowledged_count',
        'mute': 'muted_count',
    }
    for row in actions:
        team_id = actor_to_team.get(row.actor) or 'unassigned'
        if requester.get('role') == 'team_lead' and requester.get('team_id') != team_id:
            continue
        day = row.created_at.strftime('%Y-%m-%d')
        key = (day, team_id)
        field = action_map.get(row.action_type)
        if field:
            daily[key][field] += 1
    daily_items = [
        {'day': day, 'team_id': team_id, **vals}
        for (day, team_id), vals in sorted(daily.items())
    ]
    return {'windows': window_items, 'daily_team_trends': daily_items}
