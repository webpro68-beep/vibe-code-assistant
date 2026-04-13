"""template factory layer

Revision ID: 20260412_0020_template_factory_layer
Revises: 20260412_0019
Create Date: 2026-04-07 12:30:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260412_0020"
down_revision = "20260412_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "template_packs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_name", sa.Text(), nullable=False),
        sa.Column("template_type", sa.Text(), nullable=False, server_default=sa.text("'composite'")),
        sa.Column("source_project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reusability_score", sa.Numeric(5,2), nullable=True),
        sa.Column("performance_score", sa.Numeric(5,2), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "template_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_pack_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("template_packs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("change_notes", sa.Text(), nullable=True),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for name, extra_cols in {
        "style_templates": [
            sa.Column("aspect_ratio", sa.Text(), nullable=False),
            sa.Column("visual_identity_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("prompt_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("default_scene_count", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("default_duration_sec", sa.Numeric(10,2), nullable=False, server_default="5.0"),
            sa.Column("voice_profile_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("thumbnail_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        ],
        "narrative_templates": [
            sa.Column("hook_formula", sa.Text(), nullable=True),
            sa.Column("structure_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("slot_schema_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("cta_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        ],
        "scene_blueprints": [
            sa.Column("scene_count", sa.Integer(), nullable=False),
            sa.Column("blueprint_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("timeline_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        ],
        "character_packs": [
            sa.Column("identity_summary", sa.Text(), nullable=True),
            sa.Column("appearance_lock_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("reference_assets_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("pose_variants_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("expression_variants_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("usage_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        ],
        "thumbnail_templates": [
            sa.Column("layout_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("headline_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("crop_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        ],
        "publishing_templates": [
            sa.Column("platform", sa.Text(), nullable=False),
            sa.Column("publishing_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("title_pattern", sa.Text(), nullable=True),
            sa.Column("description_pattern", sa.Text(), nullable=True),
            sa.Column("hashtags_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("upload_defaults_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        ]
    }.items():
        op.create_table(
            name,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("name" if name != "character_packs" else "pack_name", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            *extra_cols,
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    op.create_table(
        "template_components",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("template_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_type", sa.Text(), nullable=False),
        sa.Column("component_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("component_role", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "template_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_pack_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("template_packs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("extraction_report_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("score_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "template_usage_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_pack_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("template_packs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("template_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False, server_default=sa.text("'single'")),
        sa.Column("input_slots_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "template_performance_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_pack_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("template_packs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "template_clone_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_pack_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("template_packs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False, server_default=sa.text("'batch'")),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("idx_template_packs_status", "template_packs", ["status"])
    op.create_index("idx_template_versions_pack_active", "template_versions", ["template_pack_id", "is_active"])
    op.create_index("idx_template_usage_runs_pack_status", "template_usage_runs", ["template_pack_id", "status"])
    op.create_index("idx_template_extractions_source_project", "template_extractions", ["source_project_id"])
    op.create_index("idx_template_clone_jobs_status", "template_clone_jobs", ["status"])
    op.create_index("idx_template_components_version_type", "template_components", ["template_version_id", "component_type"])
    op.create_index("idx_template_perf_snapshots_pack_time", "template_performance_snapshots", ["template_pack_id", "captured_at"])


def downgrade() -> None:
    for idx, table in [
        ("idx_template_perf_snapshots_pack_time", "template_performance_snapshots"),
        ("idx_template_components_version_type", "template_components"),
        ("idx_template_clone_jobs_status", "template_clone_jobs"),
        ("idx_template_extractions_source_project", "template_extractions"),
        ("idx_template_usage_runs_pack_status", "template_usage_runs"),
        ("idx_template_versions_pack_active", "template_versions"),
        ("idx_template_packs_status", "template_packs"),
    ]:
        op.drop_index(idx, table_name=table)
    for table in [
        "template_clone_jobs",
        "template_performance_snapshots",
        "template_usage_runs",
        "template_extractions",
        "template_components",
        "publishing_templates",
        "thumbnail_templates",
        "character_packs",
        "scene_blueprints",
        "narrative_templates",
        "style_templates",
        "template_versions",
        "template_packs",
    ]:
        op.drop_table(table)
