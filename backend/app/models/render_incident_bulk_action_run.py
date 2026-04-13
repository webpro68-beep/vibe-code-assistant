from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RenderIncidentBulkActionRun(Base):
    __tablename__ = "render_incident_bulk_action_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(64), nullable=False, default="operator")
    actor_team_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="apply", index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    filters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    request_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    attempted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
