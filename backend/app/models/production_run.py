from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductionRun(Base):
    __tablename__ = "production_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    render_job_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="render_job")
    current_stage: Mapped[str] = mapped_column(String(64), default="queued", index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    percent_complete: Mapped[int] = mapped_column(Integer, default=0)

    blocking_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active_worker: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    output_readiness: Mapped[str] = mapped_column(String(32), default="not_ready")
    output_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    last_event_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
