"""create render_jobs and scene_tasks

Revision ID: 20260408_0001
Revises: None
Create Date: 2026-04-08 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260408_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "render_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("queue_name", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("provider_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("worker_hint", sa.Text(), nullable=True),
        sa.Column("depends_on_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("runtime_metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="ck_render_jobs_progress_percent"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_render_jobs_attempt_count"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_render_jobs_max_attempts"),
    )

    op.create_index("ix_render_jobs_project_id", "render_jobs", ["project_id"], unique=False)
    op.create_index("ix_render_jobs_status", "render_jobs", ["status"], unique=False)
    op.create_index("ix_render_jobs_job_type", "render_jobs", ["job_type"], unique=False)
    op.create_index("ix_render_jobs_queue_name", "render_jobs", ["queue_name"], unique=False)
    op.create_index("ix_render_jobs_provider", "render_jobs", ["provider"], unique=False)
    op.create_index("ix_render_jobs_priority", "render_jobs", ["priority"], unique=False)
    op.create_index("ix_render_jobs_scheduled_at", "render_jobs", ["scheduled_at"], unique=False)
    op.create_index("ix_render_jobs_created_at", "render_jobs", ["created_at"], unique=False)
    op.create_index("ix_render_jobs_depends_on_job_id", "render_jobs", ["depends_on_job_id"], unique=False)
    op.create_index("ix_render_jobs_provider_account_id", "render_jobs", ["provider_account_id"], unique=False)
    op.create_index("ix_render_jobs_idempotency_key", "render_jobs", ["idempotency_key"], unique=True)

    op.create_table(
        "scene_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scene_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scenes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "render_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("render_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("provider_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_task_id", sa.Text(), nullable=True),
        sa.Column("provider_status", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column("negative_prompt_text", sa.Text(), nullable=True),
        sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("runtime_metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="ck_scene_tasks_progress_percent"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_scene_tasks_attempt_count"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_scene_tasks_max_attempts"),
    )

    op.create_index("ix_scene_tasks_project_id", "scene_tasks", ["project_id"], unique=False)
    op.create_index("ix_scene_tasks_scene_id", "scene_tasks", ["scene_id"], unique=False)
    op.create_index("ix_scene_tasks_render_job_id", "scene_tasks", ["render_job_id"], unique=False)
    op.create_index("ix_scene_tasks_task_type", "scene_tasks", ["task_type"], unique=False)
    op.create_index("ix_scene_tasks_status", "scene_tasks", ["status"], unique=False)
    op.create_index("ix_scene_tasks_provider", "scene_tasks", ["provider"], unique=False)
    op.create_index("ix_scene_tasks_provider_account_id", "scene_tasks", ["provider_account_id"], unique=False)
    op.create_index("ix_scene_tasks_provider_task_id", "scene_tasks", ["provider_task_id"], unique=False)
    op.create_index("ix_scene_tasks_priority", "scene_tasks", ["priority"], unique=False)
    op.create_index("ix_scene_tasks_scheduled_at", "scene_tasks", ["scheduled_at"], unique=False)
    op.create_index("ix_scene_tasks_created_at", "scene_tasks", ["created_at"], unique=False)

    op.create_index(
        "ux_scene_tasks_scene_task_type_active",
        "scene_tasks",
        ["scene_id", "task_type", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ux_scene_tasks_scene_task_type_active", table_name="scene_tasks")
    op.drop_index("ix_scene_tasks_created_at", table_name="scene_tasks")
    op.drop_index("ix_scene_tasks_scheduled_at", table_name="scene_tasks")
    op.drop_index("ix_scene_tasks_priority", table_name="scene_tasks")
    op.drop_index("ix_scene_tasks_provider_task_id", table_name="scene_tasks")
    op.drop_index("ix_scene_tasks_provider_account_id", table_name="scene_tasks")
    op.drop_index("ix_scene_tasks_provider", table_name="scene_tasks")
    op.drop_index("ix_scene_tasks_status", table_name="scene_tasks")
    op.drop_index("ix_scene_tasks_task_type", table_name="scene_tasks")
    op.drop_index("ix_scene_tasks_render_job_id", table_name="scene_tasks")
    op.drop_index("ix_scene_tasks_scene_id", table_name="scene_tasks")
    op.drop_index("ix_scene_tasks_project_id", table_name="scene_tasks")
    op.drop_table("scene_tasks")

    op.drop_index("ix_render_jobs_idempotency_key", table_name="render_jobs")
    op.drop_index("ix_render_jobs_provider_account_id", table_name="render_jobs")
    op.drop_index("ix_render_jobs_depends_on_job_id", table_name="render_jobs")
    op.drop_index("ix_render_jobs_created_at", table_name="render_jobs")
    op.drop_index("ix_render_jobs_scheduled_at", table_name="render_jobs")
    op.drop_index("ix_render_jobs_priority", table_name="render_jobs")
    op.drop_index("ix_render_jobs_provider", table_name="render_jobs")
    op.drop_index("ix_render_jobs_queue_name", table_name="render_jobs")
    op.drop_index("ix_render_jobs_job_type", table_name="render_jobs")
    op.drop_index("ix_render_jobs_status", table_name="render_jobs")
    op.drop_index("ix_render_jobs_project_id", table_name="render_jobs")
    op.drop_table("render_jobs")