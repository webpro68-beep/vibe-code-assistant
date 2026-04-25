from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TemplateGovernanceSchedule(Base):
    __tablename__ = "template_governance_schedule"
    __table_args__ = (
        UniqueConstraint("plan_id", name="uq_template_governance_schedule_plan_id"),
        Index("ix_template_governance_schedule_status", "schedule_status"),
        Index("ix_template_governance_schedule_scheduled_at", "scheduled_at"),
        Index("ix_template_governance_schedule_window_start_end", "execution_window_start", "execution_window_end"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    schedule_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unscheduled")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    allow_run_outside_window: Mapped[str] = mapped_column(String(5), nullable=False, default="false")
    missed_window_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_window_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TemplateGovernanceOrchestrationControl(Base):
    __tablename__ = "template_governance_orchestration_control"
    __table_args__ = (
        UniqueConstraint("plan_id", name="uq_template_governance_orchestration_control_plan_id"),
        Index("ix_template_governance_orchestration_control_status", "control_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    control_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    pause_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    paused_by: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    resumed_by: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    canceled_by: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TemplateGovernanceStepCooldown(Base):
    __tablename__ = "template_governance_step_cooldown"
    __table_args__ = (
        UniqueConstraint("step_id", name="uq_template_governance_step_cooldown_step_id"),
        Index("ix_template_governance_step_cooldown_next_eligible_run_at", "next_eligible_run_at"),
        Index("ix_template_governance_step_cooldown_status", "cooldown_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_eligible_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cooldown_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")

    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TemplateGovernancePostPlanEvaluation(Base):
    __tablename__ = "template_governance_post_plan_evaluation"
    __table_args__ = (
        UniqueConstraint("plan_id", name="uq_template_governance_post_plan_evaluation_plan_id"),
        Index("ix_template_governance_post_plan_evaluation_outcome_label", "outcome_label"),
        Index("ix_template_governance_post_plan_evaluation_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    outcome_label: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")

    before_metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    deltas_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    evaluation_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TemplateGovernancePolicyPromotionPath(Base):
    __tablename__ = "template_governance_policy_promotion_path"
    __table_args__ = (
        UniqueConstraint("plan_id", name="uq_template_governance_policy_promotion_path_plan_id"),
        Index("ix_template_governance_policy_promotion_path_status", "status"),
        Index("ix_template_governance_policy_promotion_path_path_type", "path_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    path_type: Mapped[str] = mapped_column(String(32), nullable=False, default="hold")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="recommended")

    confidence_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    approval_requirement_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cooldown_delta_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    recommendation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
