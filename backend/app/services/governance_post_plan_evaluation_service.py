from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.template_governance_bulk_ops import TemplateGovernanceActionOutcomeAnalytics
from app.models.template_governance_execution import TemplateGovernanceExecutionPlan
from app.models.template_governance_schedule import TemplateGovernancePostPlanEvaluation


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GovernancePostPlanEvaluationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate(self, plan_id: str) -> TemplateGovernancePostPlanEvaluation:
        plan = self.db.get(TemplateGovernanceExecutionPlan, plan_id)
        if plan is None:
            raise ValueError(f"TemplateGovernanceExecutionPlan not found: {plan_id}")

        row = self.db.scalar(
            select(TemplateGovernancePostPlanEvaluation).where(
                TemplateGovernancePostPlanEvaluation.plan_id == plan_id
            )
        )
        if row is None:
            row = TemplateGovernancePostPlanEvaluation(plan_id=plan_id)

        action_rows = self.db.scalars(
            select(TemplateGovernanceActionOutcomeAnalytics).where(
                TemplateGovernanceActionOutcomeAnalytics.bulk_operation_id == plan.bulk_operation_id
            )
        ).all()

        improved = sum(1 for x in action_rows if x.outcome_label == "improved")
        unchanged = sum(1 for x in action_rows if x.outcome_label == "unchanged")
        degraded = sum(1 for x in action_rows if x.outcome_label == "degraded")
        total = len(action_rows)

        score = 0.0
        if total > 0:
            score = ((improved * 1.0) + (unchanged * 0.25) - (degraded * 1.0)) / total

        outcome = "unknown"
        if score >= 0.5:
            outcome = "improved"
        elif score <= -0.25:
            outcome = "degraded"
        elif total > 0:
            outcome = "unchanged"

        row.status = "evaluated"
        row.outcome_label = outcome
        row.before_metrics_json = {
            "target_count": plan.target_count,
            "risk_score": plan.risk_score,
        }
        row.after_metrics_json = {
            "action_outcome_total": total,
            "improved": improved,
            "unchanged": unchanged,
            "degraded": degraded,
        }
        row.deltas_json = {
            "net_score": round(score, 4),
        }
        row.evaluation_score = round(score, 4)
        row.evaluated_at = utcnow()
        row.notes = "Automated post-plan evaluation"

        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get(self, plan_id: str) -> TemplateGovernancePostPlanEvaluation | None:
        return self.db.scalar(
            select(TemplateGovernancePostPlanEvaluation).where(
                TemplateGovernancePostPlanEvaluation.plan_id == plan_id
            )
        )
