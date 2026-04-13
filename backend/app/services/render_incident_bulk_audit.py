from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.render_incident_bulk_action_item import RenderIncidentBulkActionItem
from app.models.render_incident_bulk_action_run import RenderIncidentBulkActionRun


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


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


def create_bulk_action_run(db: Session, *, action_type: str, actor: str, actor_role: str, actor_team_id: str | None, mode: str, reason: str | None, filters: dict[str, Any], request: dict[str, Any]) -> RenderIncidentBulkActionRun:
    row = RenderIncidentBulkActionRun(id=_new_id("bulkrun"), action_type=action_type, actor=actor, actor_role=actor_role, actor_team_id=actor_team_id, mode=mode, reason=reason, filters_json=_dump_json(filters), request_json=_dump_json(request), attempted=0, succeeded=0, failed=0)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def finalize_bulk_action_run(db: Session, *, run: RenderIncidentBulkActionRun, results: list[dict[str, Any]]) -> RenderIncidentBulkActionRun:
    run.attempted = len(results)
    run.succeeded = sum(1 for item in results if item.get("ok"))
    run.failed = run.attempted - run.succeeded
    db.add(run)
    for item in results:
        db.add(RenderIncidentBulkActionItem(id=_new_id("bulkitem"), run_id=run.id, incident_key=item["incident_key"], ok="true" if item.get("ok") else "false", status=item.get("status"), error=item.get("error"), payload_json=_dump_json(item)))
    db.commit()
    db.refresh(run)
    return run


def serialize_run(row: RenderIncidentBulkActionRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "action_type": row.action_type,
        "actor": row.actor,
        "actor_role": row.actor_role,
        "actor_team_id": row.actor_team_id,
        "mode": row.mode,
        "reason": row.reason,
        "attempted": row.attempted,
        "succeeded": row.succeeded,
        "failed": row.failed,
        "filters": _load_json(row.filters_json),
        "request": _load_json(row.request_json),
        "created_at": row.created_at,
    }


def serialize_item(row: RenderIncidentBulkActionItem) -> dict[str, Any]:
    return {
        "incident_key": row.incident_key,
        "ok": row.ok == "true",
        "status": row.status,
        "error": row.error,
        "payload": _load_json(row.payload_json),
        "created_at": row.created_at,
    }


def list_bulk_action_runs(db: Session, *, actor: str | None = None, team_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    q = db.query(RenderIncidentBulkActionRun)
    if actor and team_id:
        q = q.filter(or_(RenderIncidentBulkActionRun.actor == actor, RenderIncidentBulkActionRun.actor_team_id == team_id))
    elif actor:
        q = q.filter(RenderIncidentBulkActionRun.actor == actor)
    elif team_id:
        q = q.filter(RenderIncidentBulkActionRun.actor_team_id == team_id)
    rows = q.order_by(RenderIncidentBulkActionRun.created_at.desc()).limit(limit).all()
    return [serialize_run(r) for r in rows]


def get_bulk_action_run_detail(db: Session, *, run_id: str) -> dict[str, Any] | None:
    run = db.query(RenderIncidentBulkActionRun).filter(RenderIncidentBulkActionRun.id == run_id).first()
    if not run:
        return None
    items = db.query(RenderIncidentBulkActionItem).filter(RenderIncidentBulkActionItem.run_id == run_id).order_by(RenderIncidentBulkActionItem.created_at.desc()).all()
    return {"run": serialize_run(run), "items": [serialize_item(i) for i in items]}
