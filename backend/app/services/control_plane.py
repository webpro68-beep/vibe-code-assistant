from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings

from app.models.decision_execution_audit_log import DecisionExecutionAuditLog
from app.models.provider_routing_override import ProviderRoutingOverride
from app.models.release_gate_state import ReleaseGateState
from app.models.worker_concurrency_override import WorkerConcurrencyOverride


DEFAULT_QUEUE_NAME = "render.dispatch"
DEFAULT_RELEASE_GATE = "render-release"


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def get_or_create_worker_override(db: Session, *, queue_name: str = DEFAULT_QUEUE_NAME) -> WorkerConcurrencyOverride:
    row = db.query(WorkerConcurrencyOverride).filter(WorkerConcurrencyOverride.queue_name == queue_name).first()
    if row:
        return row
    row = WorkerConcurrencyOverride(
        id=str(uuid.uuid4()),
        queue_name=queue_name,
        dispatch_batch_limit=settings.default_dispatch_batch_limit,
        poll_countdown_seconds=settings.default_poll_countdown_seconds,
        enabled=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def set_worker_override(
    db: Session,
    *,
    actor: str,
    queue_name: str = DEFAULT_QUEUE_NAME,
    dispatch_batch_limit: int | None = None,
    poll_countdown_seconds: int | None = None,
    enabled: bool | None = None,
    reason: str | None = None,
) -> WorkerConcurrencyOverride:
    row = get_or_create_worker_override(db, queue_name=queue_name)
    if dispatch_batch_limit is not None:
        row.dispatch_batch_limit = max(1, int(dispatch_batch_limit))
    if poll_countdown_seconds is not None:
        row.poll_countdown_seconds = max(5, int(poll_countdown_seconds))
    if enabled is not None:
        row.enabled = bool(enabled)
    row.updated_by = actor
    row.reason = reason
    db.commit()
    db.refresh(row)
    return row


def get_or_create_release_gate(db: Session, *, gate_name: str = DEFAULT_RELEASE_GATE) -> ReleaseGateState:
    row = db.query(ReleaseGateState).filter(ReleaseGateState.gate_name == gate_name).first()
    if row:
        return row
    row = ReleaseGateState(
        id=str(uuid.uuid4()),
        gate_name=gate_name,
        blocked=False,
        source="bootstrap",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def set_release_gate(
    db: Session,
    *,
    actor: str,
    blocked: bool,
    reason: str | None,
    source: str,
    decision_type: str | None,
    gate_name: str = DEFAULT_RELEASE_GATE,
) -> ReleaseGateState:
    row = get_or_create_release_gate(db, gate_name=gate_name)
    row.blocked = bool(blocked)
    row.reason = reason
    row.source = source
    row.updated_by = actor
    row.last_decision_type = decision_type
    db.commit()
    db.refresh(row)
    return row


def get_provider_override(db: Session, *, source_provider: str) -> ProviderRoutingOverride | None:
    row = db.query(ProviderRoutingOverride).filter(
        ProviderRoutingOverride.source_provider == source_provider,
        ProviderRoutingOverride.active.is_(True),
    ).first()
    if row and row.expires_at and row.expires_at <= datetime.utcnow():
        row.active = False
        db.commit()
        return None
    return row


def set_provider_override(
    db: Session,
    *,
    actor: str,
    source_provider: str,
    target_provider: str,
    active: bool = True,
    reason: str | None = None,
    expires_at: datetime | None = None,
) -> ProviderRoutingOverride:
    row = db.query(ProviderRoutingOverride).filter(ProviderRoutingOverride.source_provider == source_provider).first()
    if row is None:
        row = ProviderRoutingOverride(
            id=str(uuid.uuid4()),
            source_provider=source_provider,
            target_provider=target_provider,
        )
        db.add(row)
    row.target_provider = target_provider
    row.active = active
    row.reason = reason
    row.updated_by = actor
    row.expires_at = expires_at
    db.commit()
    db.refresh(row)
    return row


def resolve_effective_provider(db: Session, requested_provider: str) -> tuple[str, dict[str, Any] | None]:
    row = get_provider_override(db, source_provider=requested_provider)
    if row and row.target_provider and row.target_provider != requested_provider:
        return row.target_provider, {
            "source_provider": requested_provider,
            "target_provider": row.target_provider,
            "override_id": row.id,
            "reason": row.reason,
        }
    return requested_provider, None


def create_decision_audit_log(
    db: Session,
    *,
    decision_type: str,
    actor: str,
    execution_status: str,
    reason: str | None,
    action_payload: dict[str, Any] | None,
    result: dict[str, Any] | None,
    policy_version: str | None = None,
    recommendation_key: str | None = None,
) -> DecisionExecutionAuditLog:
    row = DecisionExecutionAuditLog(
        id=str(uuid.uuid4()),
        decision_type=decision_type,
        actor=actor,
        execution_status=execution_status,
        reason=reason,
        action_payload_json=_json_dumps(action_payload or {}),
        result_json=_json_dumps(result or {}),
        policy_version=policy_version,
        recommendation_key=recommendation_key,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
