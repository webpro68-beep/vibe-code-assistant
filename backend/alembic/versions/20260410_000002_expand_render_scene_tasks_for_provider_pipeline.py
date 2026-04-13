"""expand render scene tasks for provider pipeline

Revision ID: 20260410_000002
Revises: 20260410_000001
Create Date: 2026-04-10 20:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260410_000002"
down_revision = "20260410_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("render_scene_tasks", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("script_text", sa.Text(), nullable=True))

    op.add_column("render_scene_tasks", sa.Column("provider_target_duration_sec", sa.Float(), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("target_duration_sec", sa.Float(), nullable=True))

    op.add_column("render_scene_tasks", sa.Column("provider_mode", sa.String(length=50), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("source_scene_index", sa.Integer(), nullable=True))

    op.add_column("render_scene_tasks", sa.Column("visual_prompt", sa.Text(), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("start_image_url", sa.Text(), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("end_image_url", sa.Text(), nullable=True))

    op.add_column("render_scene_tasks", sa.Column("provider_task_id", sa.String(length=255), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("provider_operation_name", sa.String(length=255), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("provider_payload", sa.JSON(), nullable=True))

    op.add_column("render_scene_tasks", sa.Column("output_url", sa.Text(), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("output_path", sa.Text(), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_render_scene_tasks_provider_task_id", "render_scene_tasks", ["provider_task_id"])
    op.create_index("ix_render_scene_tasks_provider_operation_name", "render_scene_tasks", ["provider_operation_name"])


def downgrade() -> None:
    op.drop_index("ix_render_scene_tasks_provider_operation_name", table_name="render_scene_tasks")
    op.drop_index("ix_render_scene_tasks_provider_task_id", table_name="render_scene_tasks")

    op.drop_column("render_scene_tasks", "completed_at")
    op.drop_column("render_scene_tasks", "error_message")
    op.drop_column("render_scene_tasks", "output_path")
    op.drop_column("render_scene_tasks", "output_url")

    op.drop_column("render_scene_tasks", "provider_payload")
    op.drop_column("render_scene_tasks", "provider_operation_name")
    op.drop_column("render_scene_tasks", "provider_task_id")

    op.drop_column("render_scene_tasks", "end_image_url")
    op.drop_column("render_scene_tasks", "start_image_url")
    op.drop_column("render_scene_tasks", "visual_prompt")

    op.drop_column("render_scene_tasks", "source_scene_index")
    op.drop_column("render_scene_tasks", "provider_mode")

    op.drop_column("render_scene_tasks", "target_duration_sec")
    op.drop_column("render_scene_tasks", "provider_target_duration_sec")

    op.drop_column("render_scene_tasks", "script_text")
    op.drop_column("render_scene_tasks", "title")