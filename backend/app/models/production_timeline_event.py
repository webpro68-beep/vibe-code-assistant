from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductionTimelineEvent(Base):
    __tablename__ = "production_timeline_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    production_run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    render_job_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    phase: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    worker_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    progress_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_blocking: Mapped[bool] = mapped_column(Boolean, default=False)
    is_operator_action: Mapped[bool] = mapped_column(Boolean, default=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
