from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RenderSceneTask(Base):
    __tablename__ = "render_scene_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("render_jobs.id"), index=True)
    scene_index: Mapped[int] = mapped_column(Integer, index=True)

    title: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="queued")

    # Provider runtime fields
    provider_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    provider_region: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    provider_request_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    provider_operation_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    provider_status_raw: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    provider_callback_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Request/response payloads
    request_payload_json: Mapped[str] = mapped_column(Text)
    response_payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Provider output
    output_video_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    local_video_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Object storage
    storage_bucket: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    storage_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    storage_signed_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Failure / control
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    failure_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_polled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_callback_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    provider_status_observed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_stalled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    poll_fallback_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    job = relationship("RenderJob", back_populates="scenes")