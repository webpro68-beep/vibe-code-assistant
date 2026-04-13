"""template runtime scoring and autopick

Revision ID: 20260412_0021
Revises: 20260412_0020
Create Date: 2026-04-12 02:45:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260412_0021"
down_revision = "20260412_0020"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "template_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_pack_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("render_score", sa.Numeric(5,2), nullable=False),
        sa.Column("upload_score", sa.Numeric(5,2), nullable=False),
        sa.Column("retention_score", sa.Numeric(5,2), nullable=False),
        sa.Column("final_priority_score", sa.Numeric(5,2), nullable=False),
        sa.Column("runs_considered", sa.Integer(), nullable=False),
        sa.Column("snapshot_count", sa.Integer(), nullable=False),
        sa.Column("score_version", sa.Text(), nullable=False),
        sa.Column("scoring_window", sa.Text(), nullable=True),
        sa.Column("weight_profile", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("score_details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["template_pack_id"], ["template_packs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "template_memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_pack_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("previous_state", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("last_score", sa.Numeric(5,2), nullable=True),
        sa.Column("transition_count", sa.Integer(), nullable=False),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("demoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dominant_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stats_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["template_pack_id"], ["template_packs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_pack_id"),
    )
    op.create_table(
        "template_selection_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_pack_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision_mode", sa.Text(), nullable=False),
        sa.Column("request_context_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fit_score", sa.Numeric(5,2), nullable=False),
        sa.Column("reason_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("alternatives_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("outcome_label", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["template_pack_id"], ["template_packs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

def downgrade() -> None:
    op.drop_table("template_selection_decisions")
    op.drop_table("template_memory")
    op.drop_table("template_scores")
