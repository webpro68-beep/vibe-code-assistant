from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.template_governance_schedule import (
    TemplateGovernancePolicyPromotionPath,
    TemplateGovernancePostPlanEvaluation,
)


class GovernancePolicyPromotionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate_path(self, plan_id: str) -> TemplateGovernancePolicyPromotionPath:
        evaluation = self.db.scalar(
            select(TemplateGovernancePostPlanEvaluation).where(
                TemplateGovernancePostPlanEvaluation.plan_id == plan_id
            )
        )
        if evaluation is None:
            raise ValueError(f"TemplateGovernancePostPlanEvaluation not found for plan_id={plan_id}")

        row = self.db.scalar(
            select(TemplateGovernancePolicyPromotionPath).where(
                TemplateGovernancePolicyPromotionPath.plan_id == plan_id
            )
        )
        if row is None:
            row = TemplateGovernancePolicyPromotionPath(plan_id=plan_id)

        score = float(evaluation.evaluation_score or 0.0)

        if evaluation.outcome_label == "improved":
            row.path_type = "promote"
            row.confidence_delta = 0.10
            row.approval_requirement_delta = -1
            row.cooldown_delta_seconds = -10
            row.recommendation_reason = "Plan improved runtime outcomes; promote similar policy path."
        elif evaluation.outcome_label == "degraded":
            row.path_type = "demote"
            row.confidence_delta = -0.15
            row.approval_requirement_delta = 1
            row.cooldown_delta_seconds = 30
            row.recommendation_reason = "Plan degraded runtime outcomes; demote policy path and increase caution."
        else:
            row.path_type = "hold"
            row.confidence_delta = 0.0
            row.approval_requirement_delta = 0
            row.cooldown_delta_seconds = 0
            row.recommendation_reason = "Outcome neutral; hold current policy path."

        row.status = "recommended"
        row.payload_json = {
            "outcome_label": evaluation.outcome_label,
            "evaluation_score": score,
            "deltas_json": evaluation.deltas_json or {},
        }

        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get(self, plan_id: str) -> TemplateGovernancePolicyPromotionPath | None:
        return self.db.scalar(
            select(TemplateGovernancePolicyPromotionPath).where(
                TemplateGovernancePolicyPromotionPath.plan_id == plan_id
            )
        )
