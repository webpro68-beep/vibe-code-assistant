"""governance execution backfill

Revision ID: 20260412_0025
Revises: 20260412_0024
Create Date: 2026-04-12 06:10:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260412_0025"
down_revision = "20260412_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "template_governance_execution_plan",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_pack_id", sa.String(length=36), nullable=True),
        sa.Column("bulk_operation_id", sa.String(length=36), nullable=True),
        sa.Column("execution_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("completed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_template_governance_execution_plan_status",
        "template_governance_execution_plan",
        ["status"],
    )
    op.create_index(
        "ix_template_governance_execution_plan_created_at",
        "template_governance_execution_plan",
        ["created_at"],
    )

    op.create_table(
        "template_governance_execution_step",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("step_key", sa.String(length=128), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["template_governance_execution_plan.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_template_governance_execution_step_plan_id",
        "template_governance_execution_step",
        ["plan_id"],
    )
    op.create_index(
        "ix_template_governance_execution_step_status",
        "template_governance_execution_step",
        ["status"],
    )

    op.create_table(
        "template_governance_plan_timeline_event",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("step_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["template_governance_execution_plan.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_template_governance_plan_timeline_event_plan_id",
        "template_governance_plan_timeline_event",
        ["plan_id"],
    )
    op.create_index(
        "ix_template_governance_plan_timeline_event_event_type",
        "template_governance_plan_timeline_event",
        ["event_type"],
    )
    op.create_index(
        "ix_template_governance_plan_timeline_event_created_at",
        "template_governance_plan_timeline_event",
        ["created_at"],
    )

    op.create_table(
        "template_governance_action_outcome_analytics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("bulk_operation_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("action_type", sa.String(length=64), nullable=True),
        sa.Column("outcome_label", sa.String(length=32), nullable=False),
        sa.Column("impact_score", sa.Float(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_template_governance_action_outcome_analytics_bulk_operation_id",
        "template_governance_action_outcome_analytics",
        ["bulk_operation_id"],
    )
    op.create_index(
        "ix_template_governance_action_outcome_analytics_outcome_label",
        "template_governance_action_outcome_analytics",
        ["outcome_label"],
    )
    op.create_index(
        "ix_template_governance_action_outcome_analytics_created_at",
        "template_governance_action_outcome_analytics",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_template_governance_action_outcome_analytics_created_at",
        table_name="template_governance_action_outcome_analytics",
    )
    op.drop_index(
        "ix_template_governance_action_outcome_analytics_outcome_label",
        table_name="template_governance_action_outcome_analytics",
    )
    op.drop_index(
        "ix_template_governance_action_outcome_analytics_bulk_operation_id",
        table_name="template_governance_action_outcome_analytics",
    )
    op.drop_table("template_governance_action_outcome_analytics")

    op.drop_index(
        "ix_template_governance_plan_timeline_event_created_at",
        table_name="template_governance_plan_timeline_event",
    )
    op.drop_index(
        "ix_template_governance_plan_timeline_event_event_type",
        table_name="template_governance_plan_timeline_event",
    )
    op.drop_index(
        "ix_template_governance_plan_timeline_event_plan_id",
        table_name="template_governance_plan_timeline_event",
    )
    op.drop_table("template_governance_plan_timeline_event")

    op.drop_index(
        "ix_template_governance_execution_step_status",
        table_name="template_governance_execution_step",
    )
    op.drop_index(
        "ix_template_governance_execution_step_plan_id",
        table_name="template_governance_execution_step",
    )
    op.drop_table("template_governance_execution_step")

    op.drop_index(
        "ix_template_governance_execution_plan_created_at",
        table_name="template_governance_execution_plan",
    )
    op.drop_index(
        "ix_template_governance_execution_plan_status",
        table_name="template_governance_execution_plan",
    )
    op.drop_table("template_governance_execution_plan")