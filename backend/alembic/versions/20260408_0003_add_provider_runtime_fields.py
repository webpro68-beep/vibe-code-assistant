from alembic import op
import sqlalchemy as sa

revision = "20260408_0003"
down_revision = "20260408_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("render_scene_tasks", sa.Column("provider_model", sa.String(length=128), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("provider_region", sa.String(length=64), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("provider_request_id", sa.String(length=255), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("provider_status_raw", sa.String(length=128), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("provider_callback_url", sa.Text(), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("submitted_at", sa.DateTime(), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("finished_at", sa.DateTime(), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("last_polled_at", sa.DateTime(), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("last_callback_at", sa.DateTime(), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("render_scene_tasks", sa.Column("poll_fallback_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("render_scene_tasks", sa.Column("output_metadata_json", sa.Text(), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("failure_code", sa.String(length=128), nullable=True))
    op.add_column("render_scene_tasks", sa.Column("failure_category", sa.String(length=64), nullable=True))

    op.create_index("ix_render_scene_tasks_provider_task_id", "render_scene_tasks", ["provider_task_id"])
    op.create_index("ix_render_scene_tasks_provider_operation_name", "render_scene_tasks", ["provider_operation_name"])


def downgrade() -> None:
    op.drop_index("ix_render_scene_tasks_provider_operation_name", table_name="render_scene_tasks")
    op.drop_index("ix_render_scene_tasks_provider_task_id", table_name="render_scene_tasks")

    for col in [
        "failure_category",
        "failure_code",
        "output_metadata_json",
        "poll_fallback_enabled",
        "retry_count",
        "last_callback_at",
        "last_polled_at",
        "finished_at",
        "started_at",
        "submitted_at",
        "provider_callback_url",
        "provider_status_raw",
        "provider_request_id",
        "provider_region",
        "provider_model",
    ]:
        op.drop_column("render_scene_tasks", col)