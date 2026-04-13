from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RenderTimelineEvent(Base):
    __tablename__ = "render_timeline_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("render_jobs.id"), index=True, nullable=False)
    scene_task_id: Mapped[Optional[str]] = mapped_column(ForeignKey("render_scene_tasks.id"), index=True, nullable=True)
    scene_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    provider_status_raw: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    provider_request_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    provider_operation_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    failure_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    failure_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    signature_valid: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    processed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    event_idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("RenderJob")
    scene = relationship("RenderSceneTask")
