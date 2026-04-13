from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TemplateScore(Base):
    __tablename__ = "template_score"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    render_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    upload_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    retention_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    final_priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    score_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    reasons_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class TemplateMemory(Base):
    __tablename__ = "template_memory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    memory_state: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate", index=True)
    current_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    usage_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dominant_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    demoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    explain_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class TemplateSelectionDecision(Base):
    __tablename__ = "template_selection_decision"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    template_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    fit_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reasons_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    alternatives_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    decision_scope_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class TemplateExtractionJob(Base):
    __tablename__ = "template_extraction_job"
    __table_args__ = (
        UniqueConstraint("project_id", "source_project_fingerprint", name="uq_template_extraction_job_project_fingerprint"),
        Index("ix_template_extraction_job_status_created_at", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_render_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    source_project_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    output_template_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TemplateExtractedDraft(Base):
    __tablename__ = "template_extracted_draft"
    __table_args__ = (
        Index("ix_template_extracted_draft_status_created_at", "status", "created_at"),
        Index("ix_template_extracted_draft_scope_key", "scope_key"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    extraction_job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("template_extraction_job.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_render_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft_extracted", index=True)

    scope_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ratio: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    platform: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    scene_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    source_project_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    template_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    preview_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tags_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TemplateCompetitionRecord(Base):
    __tablename__ = "template_competition_record"
    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "compared_against_template_id",
            "scope_key",
            name="uq_template_competition_pair_scope",
        ),
        Index("ix_template_competition_scope_key", "scope_key"),
        Index("ix_template_competition_template_scope", "template_id", "scope_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    compared_against_template_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    scope_key: Mapped[str] = mapped_column(String(128), nullable=False)
    win_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    loss_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tie_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    avg_score_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_retention_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_render_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_upload_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_compared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TemplateLearningStat(Base):
    __tablename__ = "template_learning_stat"
    __table_args__ = (
        UniqueConstraint("template_id", "scope_key", name="uq_template_learning_stat_template_scope"),
        Index("ix_template_learning_stat_scope_key", "scope_key"),
        Index("ix_template_learning_stat_template_id", "template_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(128), nullable=False)

    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rerender_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    avg_render_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_upload_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_retention_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_final_priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    retry_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rerender_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_scene_failure_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    stability_index: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reuse_effectiveness: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    dominance_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    last_7d_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_30d_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trend_direction: Mapped[str] = mapped_column(String(16), nullable=False, default="flat")

    updated_from_project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class TemplateReusePreview(Base):
    __tablename__ = "template_reuse_preview"
    __table_args__ = (
        UniqueConstraint("template_id", "preview_hash", name="uq_template_reuse_preview_template_hash"),
        Index("ix_template_reuse_preview_template_id", "template_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    preview_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    preview_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    warnings_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    editable_fields_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TemplateEvolutionEvent(Base):
    __tablename__ = "template_evolution_event"
    __table_args__ = (
        Index("ix_template_evolution_event_template_id_created_at", "template_id", "created_at"),
        Index("ix_template_evolution_event_event_type", "event_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_render_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
