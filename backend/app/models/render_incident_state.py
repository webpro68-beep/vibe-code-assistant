from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RenderIncidentState(Base):
    __tablename__ = "render_incident_states"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    incident_family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    current_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    current_event_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    current_severity_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    last_transition_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", index=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    assigned_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    muted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    muted_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    muted_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mute_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suppressed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    suppression_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reopen_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reopened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
