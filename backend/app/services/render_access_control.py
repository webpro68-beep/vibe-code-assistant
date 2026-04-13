from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.render_operator_access_profile import RenderOperatorAccessProfile

ROLE_LEVEL = {"viewer": 10, "operator": 20, "team_lead": 30, "admin": 40}


def _new_id(prefix: str = "acc") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def _default_scopes(role: str) -> dict[str, Any]:
    return {
        "can_manage_shared_views": role in {"team_lead", "admin"},
        "can_run_bulk_actions": role in {"operator", "team_lead", "admin"},
        "can_view_bulk_audit": role in {"team_lead", "admin"},
        "can_manage_access_profiles": role == "admin",
    }


def _load_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _dump_json(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def serialize_access_profile(row: RenderOperatorAccessProfile) -> dict[str, Any]:
    return {
        "actor_id": row.actor_id,
        "role": row.role,
        "team_id": row.team_id,
        "is_active": row.is_active,
        "scopes": _load_json(row.scopes_json),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def get_or_create_access_profile(db: Session, *, actor: str) -> dict[str, Any]:
    row = db.query(RenderOperatorAccessProfile).filter(RenderOperatorAccessProfile.actor_id == actor).first()
    if not row:
        role = "team_lead" if actor.startswith("lead") else "operator"
        team_id = "ops" if role == "team_lead" else None
        row = RenderOperatorAccessProfile(id=_new_id(), actor_id=actor, role=role, team_id=team_id, scopes_json=_dump_json(_default_scopes(role)))
        db.add(row)
        db.commit()
        db.refresh(row)
    return serialize_access_profile(row)


def ensure_access(db: Session, *, actor: str, minimum_role: str) -> dict[str, Any]:
    profile = get_or_create_access_profile(db, actor=actor)
    if ROLE_LEVEL.get(profile["role"], 0) < ROLE_LEVEL.get(minimum_role, 0):
        raise PermissionError(f"Actor {actor} lacks required role {minimum_role}")
    return profile



def list_access_profiles(db: Session, *, actor: str, team_only: bool = False) -> list[dict[str, Any]]:
    requester = get_or_create_access_profile(db, actor=actor)
    q = db.query(RenderOperatorAccessProfile)
    if requester["role"] == "admin":
        if team_only and requester.get("team_id"):
            q = q.filter(RenderOperatorAccessProfile.team_id == requester.get("team_id"))
    elif requester["role"] == "team_lead":
        q = q.filter(RenderOperatorAccessProfile.team_id == requester.get("team_id"))
    else:
        q = q.filter(RenderOperatorAccessProfile.actor_id == actor)
    rows = q.order_by(RenderOperatorAccessProfile.team_id.asc(), RenderOperatorAccessProfile.actor_id.asc()).all()
    return [serialize_access_profile(r) for r in rows]


def update_access_profile(db: Session, *, actor: str, target_actor_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    requester = get_or_create_access_profile(db, actor=actor)
    row = db.query(RenderOperatorAccessProfile).filter(RenderOperatorAccessProfile.actor_id == target_actor_id).first()
    if not row:
        return None
    if requester["role"] == "admin":
        pass
    elif requester["role"] == "team_lead":
        if row.team_id != requester.get("team_id"):
            raise PermissionError("Cannot edit access profile outside your team")
        if "team_id" in patch and patch["team_id"] not in {None, row.team_id, requester.get("team_id")}:
            raise PermissionError("Team lead cannot move profiles across teams")
        if "role" in patch and patch["role"] == "admin":
            raise PermissionError("Team lead cannot grant admin")
    else:
        raise PermissionError("Insufficient role to edit access profiles")

    if patch.get("role") is not None:
        row.role = patch["role"]
    if "team_id" in patch:
        row.team_id = patch.get("team_id")
    if patch.get("is_active") is not None:
        row.is_active = bool(patch["is_active"])
    if patch.get("scopes") is not None:
        row.scopes_json = _dump_json(patch["scopes"])
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_access_profile(row)
