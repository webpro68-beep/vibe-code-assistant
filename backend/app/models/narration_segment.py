from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NarrationSegment(Base):
    __tablename__ = "narration_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    narration_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("narration_jobs.id"), nullable=False, index=True)
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    pause_after_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
