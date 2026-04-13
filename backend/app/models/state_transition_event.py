from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StateTransitionEvent(Base):
    __tablename__ = "state_transition_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)

    job_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    scene_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    source: Mapped[str] = mapped_column(String(64), index=True)
    old_state: Mapped[str] = mapped_column(String(64))
    new_state: Mapped[str] = mapped_column(String(64))

    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)