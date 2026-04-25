from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.template_governance_execution import TemplateGovernancePlanTimelineEvent


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GovernancePlanTimelineService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        *,
        plan_id: str,
        event_type: str,
        step_id: str | None = None,
        actor_id: str | None = None,
        status: str | None = None,
        note: str | None = None,
        payload_json: dict[str, Any] | None = None,
    ) -> TemplateGovernancePlanTimelineEvent:
        row = TemplateGovernancePlanTimelineEvent(
            plan_id=plan_id,
            step_id=step_id,
            event_type=event_type,
            actor_id=actor_id,
            status=status,
            note=note,
            payload_json=payload_json,
            created_at=utcnow(),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
