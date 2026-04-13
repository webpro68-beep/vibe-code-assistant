from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AutopilotExecutionState(Base):
    __tablename__ = "autopilot_execution_states"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    recommendation_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    last_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    last_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cooldown_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    suppression_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    last_executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    last_evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
