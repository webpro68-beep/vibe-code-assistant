from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.services.governance_scheduling_service import GovernanceSchedulingService
from app.services.governance_orchestration_control_service import GovernanceOrchestrationControlService
from app.services.governance_post_plan_evaluation_service import GovernancePostPlanEvaluationService
from app.services.governance_policy_promotion_service import GovernancePolicyPromotionService


router = APIRouter(prefix="/api/v1", tags=["template-governance-scheduling"])


class SchedulePlanRequest(BaseModel):
    scheduled_at: datetime | None = None
    execution_window_start: datetime | None = None
    execution_window_end: datetime | None = None
    allow_run_outside_window: bool = False


class PausePlanRequest(BaseModel):
    actor_id: str
    reason: str | None = None


class ResumePlanRequest(BaseModel):
    actor_id: str


class CancelPlanRequest(BaseModel):
    actor_id: str
    reason: str | None = None


@router.post("/templates/governance/execution-plans/{plan_id}/schedule")
def schedule_plan(
    plan_id: str,
    payload: SchedulePlanRequest,
    db: Session = Depends(deps.get_db),
):
    service = GovernanceSchedulingService(db=db)
    try:
        row = service.create_or_update_schedule(
            plan_id=plan_id,
            scheduled_at=payload.scheduled_at,
            execution_window_start=payload.execution_window_start,
            execution_window_end=payload.execution_window_end,
            allow_run_outside_window=payload.allow_run_outside_window,
        )
        return {
            "id": row.id,
            "plan_id": row.plan_id,
            "schedule_status": row.schedule_status,
            "scheduled_at": row.scheduled_at,
            "execution_window_start": row.execution_window_start,
            "execution_window_end": row.execution_window_end,
            "allow_run_outside_window": row.allow_run_outside_window,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/templates/governance/execution-plans/{plan_id}/pause")
def pause_plan(
    plan_id: str,
    payload: PausePlanRequest,
    db: Session = Depends(deps.get_db),
):
    service = GovernanceOrchestrationControlService(db=db)
    try:
        row = service.pause(plan_id=plan_id, actor_id=payload.actor_id, reason=payload.reason)
        return {"plan_id": row.plan_id, "control_status": row.control_status}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/templates/governance/execution-plans/{plan_id}/resume")
def resume_plan(
    plan_id: str,
    payload: ResumePlanRequest,
    db: Session = Depends(deps.get_db),
):
    service = GovernanceOrchestrationControlService(db=db)
    try:
        row = service.resume(plan_id=plan_id, actor_id=payload.actor_id)
        return {"plan_id": row.plan_id, "control_status": row.control_status}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/templates/governance/execution-plans/{plan_id}/cancel")
def cancel_plan(
    plan_id: str,
    payload: CancelPlanRequest,
    db: Session = Depends(deps.get_db),
):
    service = GovernanceOrchestrationControlService(db=db)
    try:
        row = service.cancel(plan_id=plan_id, actor_id=payload.actor_id, reason=payload.reason)
        return {"plan_id": row.plan_id, "control_status": row.control_status}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/templates/governance/execution-plans/{plan_id}/evaluate")
def evaluate_plan(
    plan_id: str,
    db: Session = Depends(deps.get_db),
):
    service = GovernancePostPlanEvaluationService(db=db)
    try:
        row = service.evaluate(plan_id=plan_id)
        return {
            "plan_id": row.plan_id,
            "status": row.status,
            "outcome_label": row.outcome_label,
            "evaluation_score": row.evaluation_score,
            "before_metrics_json": row.before_metrics_json,
            "after_metrics_json": row.after_metrics_json,
            "deltas_json": row.deltas_json,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/templates/governance/execution-plans/{plan_id}/evaluation")
def get_plan_evaluation(
    plan_id: str,
    db: Session = Depends(deps.get_db),
):
    service = GovernancePostPlanEvaluationService(db=db)
    row = service.get(plan_id=plan_id)
    if row is None:
        return None
    return {
        "plan_id": row.plan_id,
        "status": row.status,
        "outcome_label": row.outcome_label,
        "evaluation_score": row.evaluation_score,
        "before_metrics_json": row.before_metrics_json,
        "after_metrics_json": row.after_metrics_json,
        "deltas_json": row.deltas_json,
        "evaluated_at": row.evaluated_at,
    }


@router.post("/templates/governance/execution-plans/{plan_id}/policy-path/evaluate")
def evaluate_policy_path(
    plan_id: str,
    db: Session = Depends(deps.get_db),
):
    service = GovernancePolicyPromotionService(db=db)
    try:
        row = service.evaluate_path(plan_id=plan_id)
        return {
            "plan_id": row.plan_id,
            "path_type": row.path_type,
            "status": row.status,
            "confidence_delta": row.confidence_delta,
            "approval_requirement_delta": row.approval_requirement_delta,
            "cooldown_delta_seconds": row.cooldown_delta_seconds,
            "recommendation_reason": row.recommendation_reason,
            "payload_json": row.payload_json,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/templates/governance/execution-plans/{plan_id}/policy-path")
def get_policy_path(
    plan_id: str,
    db: Session = Depends(deps.get_db),
):
    service = GovernancePolicyPromotionService(db=db)
    row = service.get(plan_id=plan_id)
    if row is None:
        return None
    return {
        "plan_id": row.plan_id,
        "path_type": row.path_type,
        "status": row.status,
        "confidence_delta": row.confidence_delta,
        "approval_requirement_delta": row.approval_requirement_delta,
        "cooldown_delta_seconds": row.cooldown_delta_seconds,
        "recommendation_reason": row.recommendation_reason,
        "payload_json": row.payload_json,
    }
