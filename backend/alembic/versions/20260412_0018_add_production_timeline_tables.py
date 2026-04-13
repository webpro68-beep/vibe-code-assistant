"""add production timeline tables

Revision ID: 20260412_0018
Revises: 20260411_0017
Create Date: 2026-04-12 11:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260412_0018"
down_revision = "20260411_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("render_job_id", sa.String(length=64), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="render_job"),
        sa.Column("current_stage", sa.String(length=64), nullable=False, server_default="queued"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("percent_complete", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocking_reason", sa.Text(), nullable=True),
        sa.Column("active_worker", sa.String(length=128), nullable=True),
        sa.Column("output_readiness", sa.String(length=32), nullable=False, server_default="not_ready"),
        sa.Column("output_url", sa.Text(), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_production_runs_project_id", "production_runs", ["project_id"])
    op.create_index("ix_production_runs_render_job_id", "production_runs", ["render_job_id"], unique=True)
    op.create_index("ix_production_runs_trace_id", "production_runs", ["trace_id"])
    op.create_index("ix_production_runs_status", "production_runs", ["status"])
    op.create_index("ix_production_runs_current_stage", "production_runs", ["current_stage"])

    op.create_table(
        "production_timeline_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("production_run_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("render_job_id", sa.String(length=64), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("phase", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("worker_name", sa.String(length=128), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=True),
        sa.Column("is_blocking", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_operator_action", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for name, cols in {
        "ix_production_timeline_events_run_id": ["production_run_id"],
        "ix_production_timeline_events_project_id": ["project_id"],
        "ix_production_timeline_events_render_job_id": ["render_job_id"],
        "ix_production_timeline_events_trace_id": ["trace_id"],
        "ix_production_timeline_events_phase": ["phase"],
        "ix_production_timeline_events_stage": ["stage"],
        "ix_production_timeline_events_status": ["status"],
        "ix_production_timeline_events_occurred_at": ["occurred_at"],
    }.items():
        op.create_index(name, "production_timeline_events", cols)

    op.create_table(
        "render_job_summaries",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("render_job_id", sa.String(length=64), nullable=False),
        sa.Column("production_run_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("current_stage", sa.String(length=64), nullable=False, server_default="queued"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("percent_complete", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocking_reason", sa.Text(), nullable=True),
        sa.Column("active_worker", sa.String(length=128), nullable=True),
        sa.Column("output_readiness", sa.String(length=32), nullable=False, server_default="not_ready"),
        sa.Column("output_url", sa.Text(), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_render_job_summaries_render_job_id", "render_job_summaries", ["render_job_id"], unique=True)
    op.create_index("ix_render_job_summaries_production_run_id", "render_job_summaries", ["production_run_id"])
    op.create_index("ix_render_job_summaries_project_id", "render_job_summaries", ["project_id"])


def downgrade() -> None:
    op.drop_table("render_job_summaries")
    op.drop_table("production_timeline_events")
    op.drop_table("production_runs")
