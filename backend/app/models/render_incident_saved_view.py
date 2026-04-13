
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RenderIncidentSavedView(Base):
    __tablename__ = "render_incident_saved_views"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_actor: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    share_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="private", index=True)
    shared_team_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    allowed_roles_json: Mapped[str] = mapped_column(Text, nullable=False, default='[]')
    filters_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    sort_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
