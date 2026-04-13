from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReleaseGateState(Base):
    __tablename__ = "release_gate_states"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    gate_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_decision_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
