from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.template_governance_schedule import TemplateGovernanceSchedule


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GovernanceExecutionWindowService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def can_run_now(self, plan_id: str) -> tuple[bool, str]:
        row = self.db.scalar(
            select(TemplateGovernanceSchedule).where(
                TemplateGovernanceSchedule.plan_id == plan_id
            )
        )
        if row is None:
            return True, "no_schedule"

        now = utcnow()
        row.last_window_check_at = now
        self.db.add(row)
        self.db.commit()

        if row.allow_run_outside_window == "true":
            return True, "allowed_outside_window"

        if row.scheduled_at and now < row.scheduled_at:
            return False, "scheduled_for_future"

        if row.execution_window_start and now < row.execution_window_start:
            return False, "before_execution_window"

        if row.execution_window_end and now > row.execution_window_end:
            row.schedule_status = "missed_window"
            row.missed_window_at = now
            self.db.add(row)
            self.db.commit()
            return False, "after_execution_window"

        return True, "within_window"
