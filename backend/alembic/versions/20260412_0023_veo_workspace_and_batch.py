"""veo workspace and batch

Revision ID: 20260412_0023
Revises: 20260412_0022
Create Date: 2026-04-12 04:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260412_0023"
down_revision = "20260412_0022"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "character_reference_packs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pack_name", sa.Text(), nullable=False),
        sa.Column("owner_project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("identity_summary", sa.Text(), nullable=True),
        sa.Column("appearance_lock_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prompt_lock_tokens", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("negative_drift_tokens", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "character_reference_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_pack_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("image_role", sa.Text(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_pack_id"], ["character_reference_packs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "veo_batch_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_name", sa.Text(), nullable=False),
        sa.Column("provider_model", sa.Text(), nullable=False),
        sa.Column("veo_mode", sa.Text(), nullable=False),
        sa.Column("aspect_ratio", sa.Text(), nullable=False),
        sa.Column("target_platform", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("total_scripts", sa.Integer(), nullable=False),
        sa.Column("completed_scripts", sa.Integer(), nullable=False),
        sa.Column("failed_scripts", sa.Integer(), nullable=False),
        sa.Column("request_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "veo_batch_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("veo_batch_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("script_label", sa.Text(), nullable=True),
        sa.Column("script_text", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["veo_batch_run_id"], ["veo_batch_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

def downgrade() -> None:
    op.drop_table("veo_batch_items")
    op.drop_table("veo_batch_runs")
    op.drop_table("character_reference_images")
    op.drop_table("character_reference_packs")
