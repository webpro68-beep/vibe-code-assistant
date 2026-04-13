from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RenderIncidentAction(Base):
    __tablename__ = "render_incident_actions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
