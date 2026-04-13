from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.decision_engine import (
    DecisionEvaluationResponse,
    DecisionExecuteRequest,
    DecisionExecutionResult,
)
from app.services.decision_engine import evaluate_decision_policy, execute_decision

router = APIRouter(prefix="/api/v1/decision-engine", tags=["decision-engine"])


@router.get("/evaluate", response_model=DecisionEvaluationResponse)
async def get_decision_engine_evaluation(db: Session = Depends(get_db)):
    return evaluate_decision_policy(db)


@router.post("/execute", response_model=DecisionExecutionResult)
async def post_decision_engine_execute(payload: DecisionExecuteRequest, db: Session = Depends(get_db)):
    return execute_decision(
        db,
        decision_type=payload.decision_type,
        actor=payload.actor,
        action_payload=payload.action_payload,
        reason=payload.reason,
        dry_run=payload.dry_run,
        recommendation_key=payload.recommendation_key,
        policy_version=payload.policy_version,
    )
