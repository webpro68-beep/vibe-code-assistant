from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VoiceProfile(Base):
    __tablename__ = "voice_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="elevenlabs")
    provider_voice_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    clone_mode: Mapped[str] = mapped_column(String(64), nullable=False, default="library")
    consent_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    consent_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    language_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
