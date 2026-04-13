from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NarrationJob(Base):
    __tablename__ = "narration_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    render_job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("render_jobs.id"), nullable=True, index=True)
    voice_profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("voice_profiles.id"), nullable=False, index=True)
    script_text: Mapped[str] = mapped_column(Text, nullable=False)
    style_preset: Mapped[str] = mapped_column(String(64), nullable=False, default="natural_conversational")
    breath_pacing_preset: Mapped[str] = mapped_column(String(64), nullable=False, default="cinematic_slow")
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="elevenlabs")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    provider_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    output_local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
