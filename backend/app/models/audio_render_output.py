from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AudioRenderOutput(Base):
    __tablename__ = "audio_render_outputs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    render_job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("render_jobs.id"), nullable=True, index=True)
    narration_job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("narration_jobs.id"), nullable=True, index=True)
    music_asset_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("music_assets.id"), nullable=True, index=True)
    mix_profile_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("audio_mix_profiles.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    voice_track_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    music_track_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixed_audio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_muxed_video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_mixed_audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_muxed_video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
