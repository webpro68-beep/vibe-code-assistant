from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid.uuid4())


class TemplateGovernanceActionOutcomeAnalytics(Base):
    __tablename__ = "template_governance_action_outcome_analytics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    bulk_operation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome_label: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    impact_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
