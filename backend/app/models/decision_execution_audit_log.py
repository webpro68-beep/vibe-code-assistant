from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DecisionExecutionAuditLog(Base):
    __tablename__ = "decision_execution_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    recommendation_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
