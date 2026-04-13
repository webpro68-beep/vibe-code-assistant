"""template extraction competition learning

Revision ID: 20260412_0022
Revises: 20260412_0021
Create Date: 2026-04-12 10:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260412_0022"
down_revision = "20260412_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "template_extraction_job",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("source_render_job_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_project_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("output_template_id", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("extraction_summary_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "source_project_fingerprint", name="uq_template_extraction_job_project_fingerprint"),
    )
    op.create_index("ix_template_extraction_job_project_id", "template_extraction_job", ["project_id"], unique=False)
    op.create_index("ix_template_extraction_job_source_render_job_id", "template_extraction_job", ["source_render_job_id"], unique=False)
    op.create_index("ix_template_extraction_job_status", "template_extraction_job", ["status"], unique=False)
    op.create_index(
        "ix_template_extraction_job_status_created_at",
        "template_extraction_job",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index("ix_template_extraction_job_output_template_id", "template_extraction_job", ["output_template_id"], unique=False)

    op.create_table(
        "template_extracted_draft",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("extraction_job_id", sa.String(length=36), nullable=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("source_render_job_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=128), nullable=True),
        sa.Column("ratio", sa.String(length=32), nullable=True),
        sa.Column("platform", sa.String(length=32), nullable=True),
        sa.Column("scene_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_project_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("template_payload", sa.JSON(), nullable=False),
        sa.Column("preview_payload", sa.JSON(), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["extraction_job_id"], ["template_extraction_job.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_project_fingerprint"),
    )
    op.create_index("ix_template_extracted_draft_extraction_job_id", "template_extracted_draft", ["extraction_job_id"], unique=False)
    op.create_index("ix_template_extracted_draft_project_id", "template_extracted_draft", ["project_id"], unique=False)
    op.create_index("ix_template_extracted_draft_ratio", "template_extracted_draft", ["ratio"], unique=False)
    op.create_index("ix_template_extracted_draft_platform", "template_extracted_draft", ["platform"], unique=False)
    op.create_index("ix_template_extracted_draft_scope_key", "template_extracted_draft", ["scope_key"], unique=False)
    op.create_index(
        "ix_template_extracted_draft_status_created_at",
        "template_extracted_draft",
        ["status", "created_at"],
        unique=False,
    )

    op.create_table(
        "template_competition_record",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=64), nullable=False),
        sa.Column("compared_against_template_id", sa.String(length=64), nullable=False),
        sa.Column("scope_key", sa.String(length=128), nullable=False),
        sa.Column("win_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("loss_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tie_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_score_delta", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_retention_delta", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_render_delta", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_upload_delta", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_compared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id",
            "compared_against_template_id",
            "scope_key",
            name="uq_template_competition_pair_scope",
        ),
    )
    op.create_index("ix_template_competition_record_template_id", "template_competition_record", ["template_id"], unique=False)
    op.create_index("ix_template_competition_record_compared_against_template_id", "template_competition_record", ["compared_against_template_id"], unique=False)
    op.create_index("ix_template_competition_scope_key", "template_competition_record", ["scope_key"], unique=False)
    op.create_index("ix_template_competition_template_scope", "template_competition_record", ["template_id", "scope_key"], unique=False)

    op.create_table(
        "template_learning_stat",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=64), nullable=False),
        sa.Column("scope_key", sa.String(length=128), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rerender_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_render_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_upload_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_retention_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_final_priority_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("retry_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rerender_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_scene_failure_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stability_index", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reuse_effectiveness", sa.Float(), nullable=False, server_default="0"),
        sa.Column("dominance_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_7d_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_30d_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("trend_direction", sa.String(length=16), nullable=False, server_default="flat"),
        sa.Column("updated_from_project_id", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "scope_key", name="uq_template_learning_stat_template_scope"),
    )
    op.create_index("ix_template_learning_stat_template_id", "template_learning_stat", ["template_id"], unique=False)
    op.create_index("ix_template_learning_stat_scope_key", "template_learning_stat", ["scope_key"], unique=False)
    op.create_index("ix_template_learning_stat_updated_from_project_id", "template_learning_stat", ["updated_from_project_id"], unique=False)

    op.create_table(
        "template_reuse_preview",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=64), nullable=False),
        sa.Column("preview_hash", sa.String(length=64), nullable=False),
        sa.Column("preview_payload", sa.JSON(), nullable=False),
        sa.Column("warnings_json", sa.JSON(), nullable=True),
        sa.Column("editable_fields_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "preview_hash", name="uq_template_reuse_preview_template_hash"),
    )
    op.create_index("ix_template_reuse_preview_template_id", "template_reuse_preview", ["template_id"], unique=False)

    op.create_table(
        "template_evolution_event",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("source_project_id", sa.String(length=64), nullable=True),
        sa.Column("source_render_job_id", sa.String(length=64), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_template_evolution_event_template_id", "template_evolution_event", ["template_id"], unique=False)
    op.create_index("ix_template_evolution_event_event_type", "template_evolution_event", ["event_type"], unique=False)
    op.create_index(
        "ix_template_evolution_event_template_id_created_at",
        "template_evolution_event",
        ["template_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_template_evolution_event_template_id_created_at", table_name="template_evolution_event")
    op.drop_index("ix_template_evolution_event_event_type", table_name="template_evolution_event")
    op.drop_index("ix_template_evolution_event_template_id", table_name="template_evolution_event")
    op.drop_table("template_evolution_event")

    op.drop_index("ix_template_reuse_preview_template_id", table_name="template_reuse_preview")
    op.drop_table("template_reuse_preview")

    op.drop_index("ix_template_learning_stat_updated_from_project_id", table_name="template_learning_stat")
    op.drop_index("ix_template_learning_stat_scope_key", table_name="template_learning_stat")
    op.drop_index("ix_template_learning_stat_template_id", table_name="template_learning_stat")
    op.drop_table("template_learning_stat")

    op.drop_index("ix_template_competition_template_scope", table_name="template_competition_record")
    op.drop_index("ix_template_competition_scope_key", table_name="template_competition_record")
    op.drop_index("ix_template_competition_record_compared_against_template_id", table_name="template_competition_record")
    op.drop_index("ix_template_competition_record_template_id", table_name="template_competition_record")
    op.drop_table("template_competition_record")

    op.drop_index("ix_template_extracted_draft_status_created_at", table_name="template_extracted_draft")
    op.drop_index("ix_template_extracted_draft_scope_key", table_name="template_extracted_draft")
    op.drop_index("ix_template_extracted_draft_platform", table_name="template_extracted_draft")
    op.drop_index("ix_template_extracted_draft_ratio", table_name="template_extracted_draft")
    op.drop_index("ix_template_extracted_draft_project_id", table_name="template_extracted_draft")
    op.drop_index("ix_template_extracted_draft_extraction_job_id", table_name="template_extracted_draft")
    op.drop_table("template_extracted_draft")

    op.drop_index("ix_template_extraction_job_output_template_id", table_name="template_extraction_job")
    op.drop_index("ix_template_extraction_job_status_created_at", table_name="template_extraction_job")
    op.drop_index("ix_template_extraction_job_status", table_name="template_extraction_job")
    op.drop_index("ix_template_extraction_job_source_render_job_id", table_name="template_extraction_job")
    op.drop_index("ix_template_extraction_job_project_id", table_name="template_extraction_job")
    op.drop_table("template_extraction_job")
