from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import Text, Integer, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

def uuid_col():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

class TemplateScore(Base):
    __tablename__ = "template_scores"
    id: Mapped[uuid.UUID] = uuid_col()
    template_pack_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("template_packs.id", ondelete="CASCADE"), nullable=False)
    render_score: Mapped[float] = mapped_column(Numeric(5,2), nullable=False, default=0)
    upload_score: Mapped[float] = mapped_column(Numeric(5,2), nullable=False, default=0)
    retention_score: Mapped[float] = mapped_column(Numeric(5,2), nullable=False, default=0)
    final_priority_score: Mapped[float] = mapped_column(Numeric(5,2), nullable=False, default=0)
    runs_considered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score_version: Mapped[str] = mapped_column(Text, nullable=False, default="v1")
    scoring_window: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight_profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    score_details_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class TemplateMemory(Base):
    __tablename__ = "template_memory"
    id: Mapped[uuid.UUID] = uuid_col()
    template_pack_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("template_packs.id", ondelete="CASCADE"), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(Text, nullable=False, default="candidate")
    previous_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_score: Mapped[float | None] = mapped_column(Numeric(5,2), nullable=True)
    transition_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    demoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dominant_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stats_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class TemplateSelectionDecision(Base):
    __tablename__ = "template_selection_decisions"
    id: Mapped[uuid.UUID] = uuid_col()
    template_pack_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("template_packs.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    decision_mode: Mapped[str] = mapped_column(Text, nullable=False, default="recommend")
    request_context_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    fit_score: Mapped[float] = mapped_column(Numeric(5,2), nullable=False, default=0)
    reason_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    alternatives_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    outcome_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
