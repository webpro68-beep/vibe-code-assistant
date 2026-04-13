from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.template_governance_execution import TemplateGovernanceExecutionPlan
from app.models.template_governance_schedule import TemplateGovernanceOrchestrationControl
from app.services.governance_plan_timeline_service import GovernancePlanTimelineService


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GovernanceOrchestrationControlService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.timeline = GovernancePlanTimelineService(db=db)

    def ensure_control(self, plan_id: str) -> TemplateGovernanceOrchestrationControl:
        row = self.db.scalar(
            select(TemplateGovernanceOrchestrationControl).where(
                TemplateGovernanceOrchestrationControl.plan_id == plan_id
            )
        )
        if row is not None:
            return row

        row = TemplateGovernanceOrchestrationControl(
            plan_id=plan_id,
            control_status="active",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def pause(self, plan_id: str, actor_id: str, reason: str | None = None) -> TemplateGovernanceOrchestrationControl:
        plan = self._get_plan(plan_id)
        control = self.ensure_control(plan_id)

        control.control_status = "paused"
        control.pause_reason = reason
        control.paused_by = actor_id
        control.paused_at = utcnow()

        plan.status = "paused"

        self.db.add(control)
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(control)

        self.timeline.log(
            plan_id=plan_id,
            event_type="plan_paused",
            actor_id=actor_id,
            payload_json={"reason": reason},
        )
        return control

    def resume(self, plan_id: str, actor_id: str) -> TemplateGovernanceOrchestrationControl:
        plan = self._get_plan(plan_id)
        control = self.ensure_control(plan_id)

        control.control_status = "active"
        control.resumed_by = actor_id
        control.resumed_at = utcnow()

        if plan.status == "paused":
            plan.status = "resumed"

        self.db.add(control)
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(control)

        self.timeline.log(
            plan_id=plan_id,
            event_type="plan_resumed",
            actor_id=actor_id,
        )
        return control

    def cancel(self, plan_id: str, actor_id: str, reason: str | None = None) -> TemplateGovernanceOrchestrationControl:
        plan = self._get_plan(plan_id)
        control = self.ensure_control(plan_id)

        control.control_status = "canceled"
        control.cancel_reason = reason
        control.canceled_by = actor_id
        control.canceled_at = utcnow()

        plan.status = "canceled"

        self.db.add(control)
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(control)

        self.timeline.log(
            plan_id=plan_id,
            event_type="plan_canceled",
            actor_id=actor_id,
            payload_json={"reason": reason},
        )
        return control

    def get_control(self, plan_id: str) -> TemplateGovernanceOrchestrationControl | None:
        return self.db.scalar(
            select(TemplateGovernanceOrchestrationControl).where(
                TemplateGovernanceOrchestrationControl.plan_id == plan_id
            )
        )

    def _get_plan(self, plan_id: str) -> TemplateGovernanceExecutionPlan:
        plan = self.db.get(TemplateGovernanceExecutionPlan, plan_id)
        if plan is None:
            raise ValueError(f"TemplateGovernanceExecutionPlan not found: {plan_id}")
        return plan
