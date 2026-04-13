from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AudioMixProfile(Base):
    __tablename__ = "audio_mix_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    voice_gain_db: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    music_gain_db: Mapped[float] = mapped_column(Float, nullable=False, default=-16.0)
    ducking_strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.75)
    normalize_lufs: Mapped[float] = mapped_column(Float, nullable=False, default=-16.0)
    fade_in_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    fade_out_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=800)
    enable_ducking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
