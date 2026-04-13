from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import Text, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

def uuid_col():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

class CharacterReferencePack(Base):
    __tablename__ = "character_reference_packs"
    id: Mapped[uuid.UUID] = uuid_col()
    pack_name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    identity_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    appearance_lock_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    prompt_lock_tokens: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    negative_drift_tokens: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class CharacterReferenceImage(Base):
    __tablename__ = "character_reference_images"
    id: Mapped[uuid.UUID] = uuid_col()
    character_pack_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("character_reference_packs.id", ondelete="CASCADE"), nullable=False)
    image_role: Mapped[str] = mapped_column(Text, nullable=False, default="hero")
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class VeoBatchRun(Base):
    __tablename__ = "veo_batch_runs"
    id: Mapped[uuid.UUID] = uuid_col()
    batch_name: Mapped[str] = mapped_column(Text, nullable=False)
    provider_model: Mapped[str] = mapped_column(Text, nullable=False)
    veo_mode: Mapped[str] = mapped_column(Text, nullable=False, default="text_to_video")
    aspect_ratio: Mapped[str] = mapped_column(Text, nullable=False, default="9:16")
    target_platform: Mapped[str] = mapped_column(Text, nullable=False, default="shorts")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    total_scripts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_scripts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_scripts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

class VeoBatchItem(Base):
    __tablename__ = "veo_batch_items"
    id: Mapped[uuid.UUID] = uuid_col()
    veo_batch_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("veo_batch_runs.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    script_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    script_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
