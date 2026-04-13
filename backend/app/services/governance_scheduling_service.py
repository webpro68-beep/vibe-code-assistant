from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.template_governance_execution import TemplateGovernanceExecutionPlan
from app.models.template_governance_schedule import TemplateGovernanceSchedule
from app.services.governance_plan_timeline_service import GovernancePlanTimelineService


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GovernanceSchedulingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.timeline = GovernancePlanTimelineService(db=db)

    def create_or_update_schedule(
        self,
        plan_id: str,
        scheduled_at: datetime | None = None,
        execution_window_start: datetime | None = None,
        execution_window_end: datetime | None = None,
        allow_run_outside_window: bool = False,
    ) -> TemplateGovernanceSchedule:
        plan = self.db.get(TemplateGovernanceExecutionPlan, plan_id)
        if plan is None:
            raise ValueError(f"TemplateGovernanceExecutionPlan not found: {plan_id}")

        row = self.db.scalar(
            select(TemplateGovernanceSchedule).where(
                TemplateGovernanceSchedule.plan_id == plan_id
            )
        )
        if row is None:
            row = TemplateGovernanceSchedule(plan_id=plan_id)

        row.scheduled_at = scheduled_at
        row.execution_window_start = execution_window_start
        row.execution_window_end = execution_window_end
        row.allow_run_outside_window = "true" if allow_run_outside_window else "false"

        if scheduled_at or execution_window_start or execution_window_end:
            row.schedule_status = "scheduled"
            plan.status = "scheduled"
        else:
            row.schedule_status = "unscheduled"

        self.db.add(row)
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(row)

        self.timeline.log(
            plan_id=plan_id,
            event_type="schedule_updated",
            payload_json={
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
                "execution_window_start": execution_window_start.isoformat() if execution_window_start else None,
                "execution_window_end": execution_window_end.isoformat() if execution_window_end else None,
                "allow_run_outside_window": allow_run_outside_window,
            },
        )
        return row

    def get_schedule(self, plan_id: str) -> TemplateGovernanceSchedule | None:
        return self.db.scalar(
            select(TemplateGovernanceSchedule).where(
                TemplateGovernanceSchedule.plan_id == plan_id
            )
        )
