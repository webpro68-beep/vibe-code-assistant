from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MusicAsset(Base):
    __tablename__ = "music_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_mode: Mapped[str] = mapped_column(String(64), nullable=False, default="library")
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_asset_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    mood: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    force_instrumental: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
