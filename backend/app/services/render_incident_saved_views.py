from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.render_incident_saved_view import RenderIncidentSavedView
from app.services.render_access_control import ensure_access, get_or_create_access_profile


VALID_SHARE_SCOPES = {"private", "shared_all", "team", "role"}


def _new_id(prefix: str = "iview") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def _load_filters(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _load_roles(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _dump_filters(filters: dict[str, Any] | None) -> str:
    return json.dumps(filters or {}, ensure_ascii=False)


def _dump_roles(roles: list[str] | None) -> str:
    return json.dumps(roles or [], ensure_ascii=False)


def serialize_saved_view(row: RenderIncidentSavedView) -> dict[str, Any]:
    return {
        'id': row.id,
        'owner_actor': row.owner_actor,
        'name': row.name,
        'description': row.description,
        'is_shared': row.is_shared,
        'share_scope': row.share_scope,
        'shared_team_id': row.shared_team_id,
        'allowed_roles': _load_roles(row.allowed_roles_json),
        'filters': _load_filters(row.filters_json),
        'sort_key': row.sort_key,
        'created_at': row.created_at,
        'updated_at': row.updated_at,
    }


def _can_view(row: RenderIncidentSavedView, profile: dict[str, Any]) -> bool:
    if row.owner_actor == profile["actor_id"]:
        return True
    if row.share_scope == "shared_all" or row.is_shared:
        return True
    if row.share_scope == "team" and profile.get("team_id") and row.shared_team_id == profile.get("team_id"):
        return True
    if row.share_scope == "role" and profile.get("role") in _load_roles(row.allowed_roles_json):
        return True
    return False


def list_saved_views(db: Session, *, actor: str | None = None) -> list[dict[str, Any]]:
    q = db.query(RenderIncidentSavedView)
    rows = q.order_by(RenderIncidentSavedView.updated_at.desc()).all()
    if not actor:
        return [serialize_saved_view(i) for i in rows if i.share_scope in {"shared_all"} or i.is_shared]
    profile = get_or_create_access_profile(db, actor=actor)
    return [serialize_saved_view(i) for i in rows if _can_view(i, profile)]


def create_saved_view(db: Session, *, owner_actor: str, name: str, description: str | None, is_shared: bool, share_scope: str, shared_team_id: str | None, allowed_roles: list[str], filters: dict[str, Any], sort_key: str | None) -> dict[str, Any]:
    profile = get_or_create_access_profile(db, actor=owner_actor)
    share_scope = share_scope if share_scope in VALID_SHARE_SCOPES else "private"
    if share_scope in {"shared_all", "team", "role"}:
        ensure_access(db, actor=owner_actor, minimum_role="team_lead")
        is_shared = True
    row = RenderIncidentSavedView(id=_new_id(), owner_actor=owner_actor, name=name, description=description, is_shared=is_shared, share_scope=share_scope, shared_team_id=shared_team_id or profile.get("team_id"), allowed_roles_json=_dump_roles(allowed_roles), filters_json=_dump_filters(filters), sort_key=sort_key)
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_saved_view(row)


def update_saved_view(db: Session, *, view_id: str, actor: str | None = None, patch: dict[str, Any]) -> dict[str, Any] | None:
    row = db.query(RenderIncidentSavedView).filter(RenderIncidentSavedView.id == view_id).first()
    if not row:
        return None
    if actor and row.owner_actor != actor:
        profile = get_or_create_access_profile(db, actor=actor)
        if profile.get("role") != "admin":
            return None
    if patch.get("share_scope") in {"shared_all", "team", "role"} and actor:
        ensure_access(db, actor=actor, minimum_role="team_lead")
    for key in ['name','description','is_shared','sort_key','share_scope','shared_team_id']:
        if key in patch and patch[key] is not None:
            setattr(row, key, patch[key])
    if 'allowed_roles' in patch and patch['allowed_roles'] is not None:
        row.allowed_roles_json = _dump_roles(patch['allowed_roles'])
    if 'filters' in patch and patch['filters'] is not None:
        row.filters_json = _dump_filters(patch['filters'])
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_saved_view(row)


def delete_saved_view(db: Session, *, view_id: str, actor: str | None = None) -> bool:
    row = db.query(RenderIncidentSavedView).filter(RenderIncidentSavedView.id == view_id).first()
    if not row:
        return False
    if actor and row.owner_actor != actor:
        profile = get_or_create_access_profile(db, actor=actor)
        if profile.get("role") != "admin":
            return False
    db.delete(row)
    db.commit()
    return True
