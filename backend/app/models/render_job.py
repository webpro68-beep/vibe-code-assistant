from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RenderJob(Base):
    __tablename__ = "render_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(20), nullable=False, default="16:9")
    style_preset: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subtitle_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    merge_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    planned_scene_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_scene_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_scene_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtitle_segments: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    final_timeline: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    final_timeline_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow)
    final_storage_bucket: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    final_storage_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_signed_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    health_status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    health_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_scene_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_scene_count_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stalled_scene_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    degraded_scene_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_scene_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_health_transition_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scenes = relationship(
        "RenderSceneTask",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
