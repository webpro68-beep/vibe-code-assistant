from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RenderIncidentBulkActionItem(Base):
    __tablename__ = "render_incident_bulk_action_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    incident_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ok: Mapped[str] = mapped_column(String(8), nullable=False, default="true")
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
