from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.template_governance_execution import TemplateGovernanceExecutionStep
from app.models.template_governance_schedule import TemplateGovernanceStepCooldown


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GovernanceStepCooldownService:
    DEFAULT_COOLDOWN_SECONDS = 30

    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure(self, plan_id: str, step_id: str, cooldown_seconds: int | None = None) -> TemplateGovernanceStepCooldown:
        row = self.db.scalar(
            select(TemplateGovernanceStepCooldown).where(
                TemplateGovernanceStepCooldown.step_id == step_id
            )
        )
        if row is not None:
            return row

        row = TemplateGovernanceStepCooldown(
            plan_id=plan_id,
            step_id=step_id,
            cooldown_seconds=int(cooldown_seconds if cooldown_seconds is not None else self.DEFAULT_COOLDOWN_SECONDS),
            cooldown_status="ready",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def mark_started(self, plan_id: str, step_id: str, cooldown_seconds: int | None = None) -> TemplateGovernanceStepCooldown:
        row = self.ensure(plan_id=plan_id, step_id=step_id, cooldown_seconds=cooldown_seconds)
        row.last_started_at = utcnow()
        row.cooldown_status = "running"
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def mark_finished(self, plan_id: str, step_id: str, cooldown_seconds: int | None = None) -> TemplateGovernanceStepCooldown:
        row = self.ensure(plan_id=plan_id, step_id=step_id, cooldown_seconds=cooldown_seconds)
        now = utcnow()
        row.last_finished_at = now
        row.next_eligible_run_at = now + timedelta(seconds=int(row.cooldown_seconds or self.DEFAULT_COOLDOWN_SECONDS))
        row.cooldown_status = "cooldown"
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def can_run(self, plan_id: str, step_id: str) -> tuple[bool, str]:
        row = self.ensure(plan_id=plan_id, step_id=step_id)
        now = utcnow()

        if row.cooldown_status == "ready":
            return True, "ready"

        if row.next_eligible_run_at and now < row.next_eligible_run_at:
            return False, "cooldown_active"

        row.cooldown_status = "ready"
        self.db.add(row)
        self.db.commit()
        return True, "cooldown_expired"
