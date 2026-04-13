from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.decision_execution_audit_log import DecisionExecutionAuditLog
from app.schemas.control_plane import (
    DecisionAuditLogResponse,
    ProviderOverrideResponse,
    ProviderOverrideUpdateRequest,
    ReleaseGateResponse,
    ReleaseGateUpdateRequest,
    WorkerOverrideResponse,
    WorkerOverrideUpdateRequest,
)
from app.services.control_plane import (
    get_or_create_release_gate,
    get_or_create_worker_override,
    set_provider_override,
    set_release_gate,
    set_worker_override,
)

router = APIRouter(prefix="/api/v1/control-plane", tags=["control-plane"])


@router.get("/worker-override", response_model=WorkerOverrideResponse)
async def get_worker_override(queue_name: str = "render.dispatch", db: Session = Depends(get_db)):
    row = get_or_create_worker_override(db, queue_name=queue_name)
    return WorkerOverrideResponse(
        queue_name=row.queue_name,
        dispatch_batch_limit=row.dispatch_batch_limit,
        poll_countdown_seconds=row.poll_countdown_seconds,
        enabled=row.enabled,
        reason=row.reason,
        updated_by=row.updated_by,
    )


@router.post("/worker-override", response_model=WorkerOverrideResponse)
async def post_worker_override(payload: WorkerOverrideUpdateRequest, db: Session = Depends(get_db)):
    row = set_worker_override(
        db,
        actor=payload.actor,
        queue_name=payload.queue_name,
        dispatch_batch_limit=payload.dispatch_batch_limit,
        poll_countdown_seconds=payload.poll_countdown_seconds,
        enabled=payload.enabled,
        reason=payload.reason,
    )
    return WorkerOverrideResponse(
        queue_name=row.queue_name,
        dispatch_batch_limit=row.dispatch_batch_limit,
        poll_countdown_seconds=row.poll_countdown_seconds,
        enabled=row.enabled,
        reason=row.reason,
        updated_by=row.updated_by,
    )


@router.post("/provider-routing", response_model=ProviderOverrideResponse)
async def post_provider_override(payload: ProviderOverrideUpdateRequest, db: Session = Depends(get_db)):
    row = set_provider_override(
        db,
        actor=payload.actor,
        source_provider=payload.source_provider,
        target_provider=payload.target_provider,
        active=payload.active,
        reason=payload.reason,
        expires_at=payload.expires_at,
    )
    return ProviderOverrideResponse(
        source_provider=row.source_provider,
        target_provider=row.target_provider,
        active=row.active,
        reason=row.reason,
        updated_by=row.updated_by,
        expires_at=row.expires_at,
    )


@router.get("/release-gate", response_model=ReleaseGateResponse)
async def get_release_gate(gate_name: str = "render-release", db: Session = Depends(get_db)):
    row = get_or_create_release_gate(db, gate_name=gate_name)
    return ReleaseGateResponse(
        gate_name=row.gate_name,
        blocked=row.blocked,
        reason=row.reason,
        source=row.source,
        updated_by=row.updated_by,
        last_decision_type=row.last_decision_type,
    )


@router.post("/release-gate", response_model=ReleaseGateResponse)
async def post_release_gate(payload: ReleaseGateUpdateRequest, db: Session = Depends(get_db)):
    row = set_release_gate(
        db,
        actor=payload.actor,
        blocked=payload.blocked,
        reason=payload.reason,
        source=payload.source,
        decision_type="manual_release_gate_update",
    )
    return ReleaseGateResponse(
        gate_name=row.gate_name,
        blocked=row.blocked,
        reason=row.reason,
        source=row.source,
        updated_by=row.updated_by,
        last_decision_type=row.last_decision_type,
    )


@router.get("/decision-audit", response_model=list[DecisionAuditLogResponse])
async def list_decision_audit_logs(limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(DecisionExecutionAuditLog)
        .order_by(DecisionExecutionAuditLog.created_at.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return [
        DecisionAuditLogResponse(
            id=row.id,
            decision_type=row.decision_type,
            actor=row.actor,
            execution_status=row.execution_status,
            reason=row.reason,
            action_payload_json=row.action_payload_json,
            result_json=row.result_json,
            policy_version=row.policy_version,
            recommendation_key=row.recommendation_key,
            created_at=row.created_at,
        )
        for row in rows
    ]
