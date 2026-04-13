from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

def uuid_col():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

class TemplatePack(Base):
    __tablename__ = "template_packs"
    id: Mapped[uuid.UUID] = uuid_col()
    template_name: Mapped[str] = mapped_column(Text, nullable=False)
    template_type: Mapped[str] = mapped_column(Text, nullable=False, default="composite")
    source_project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reusability_score: Mapped[float | None] = mapped_column(Numeric(5,2), nullable=True)
    performance_score: Mapped[float | None] = mapped_column(Numeric(5,2), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class TemplateVersion(Base):
    __tablename__ = "template_versions"
    id: Mapped[uuid.UUID] = uuid_col()
    template_pack_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("template_packs.id", ondelete="CASCADE"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    change_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class StyleTemplate(Base):
    __tablename__ = "style_templates"
    id: Mapped[uuid.UUID] = uuid_col()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    aspect_ratio: Mapped[str] = mapped_column(String(16), nullable=False)
    visual_identity_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    prompt_rules_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    default_scene_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    default_duration_sec: Mapped[float] = mapped_column(Numeric(10,2), nullable=False, default=5.0)
    voice_profile_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    thumbnail_rules_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class NarrativeTemplate(Base):
    __tablename__ = "narrative_templates"
    id: Mapped[uuid.UUID] = uuid_col()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hook_formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    structure_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    slot_schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    cta_rules_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class SceneBlueprint(Base):
    __tablename__ = "scene_blueprints"
    id: Mapped[uuid.UUID] = uuid_col()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene_count: Mapped[int] = mapped_column(Integer, nullable=False)
    blueprint_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    timeline_rules_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class CharacterPack(Base):
    __tablename__ = "character_packs"
    id: Mapped[uuid.UUID] = uuid_col()
    pack_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    identity_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    appearance_lock_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reference_assets_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    pose_variants_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    expression_variants_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    usage_rules_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class ThumbnailTemplate(Base):
    __tablename__ = "thumbnail_templates"
    id: Mapped[uuid.UUID] = uuid_col()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    headline_rules_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    crop_rules_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class PublishingTemplate(Base):
    __tablename__ = "publishing_templates"
    id: Mapped[uuid.UUID] = uuid_col()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    publishing_rules_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    title_pattern: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_pattern: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    upload_defaults_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class TemplateComponent(Base):
    __tablename__ = "template_components"
    id: Mapped[uuid.UUID] = uuid_col()
    template_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("template_versions.id", ondelete="CASCADE"), nullable=False)
    component_type: Mapped[str] = mapped_column(Text, nullable=False)
    component_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    component_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class TemplateExtraction(Base):
    __tablename__ = "template_extractions"
    id: Mapped[uuid.UUID] = uuid_col()
    source_project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    template_pack_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("template_packs.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    extraction_report_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    score_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class TemplateUsageRun(Base):
    __tablename__ = "template_usage_runs"
    id: Mapped[uuid.UUID] = uuid_col()
    template_pack_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("template_packs.id", ondelete="CASCADE"), nullable=False)
    template_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("template_versions.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False, default="single")
    input_slots_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class TemplatePerformanceSnapshot(Base):
    __tablename__ = "template_performance_snapshots"
    id: Mapped[uuid.UUID] = uuid_col()
    template_pack_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("template_packs.id", ondelete="CASCADE"), nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class TemplateCloneJob(Base):
    __tablename__ = "template_clone_jobs"
    id: Mapped[uuid.UUID] = uuid_col()
    template_pack_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("template_packs.id", ondelete="CASCADE"), nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False, default="batch")
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
