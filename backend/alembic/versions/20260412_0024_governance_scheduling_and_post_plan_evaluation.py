"""governance scheduling and post plan evaluation

Revision ID: 20260412_0024
Revises: 20260412_0023
Create Date: 2026-04-12 17:10:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260412_0024"
down_revision = "20260412_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "template_governance_schedule",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("schedule_status", sa.String(length=32), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("allow_run_outside_window", sa.String(length=5), nullable=False, server_default="false"),
        sa.Column("missed_window_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_window_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", name="uq_template_governance_schedule_plan_id"),
    )
    op.create_index("ix_template_governance_schedule_status", "template_governance_schedule", ["schedule_status"], unique=False)
    op.create_index("ix_template_governance_schedule_scheduled_at", "template_governance_schedule", ["scheduled_at"], unique=False)
    op.create_index("ix_template_governance_schedule_window_start_end", "template_governance_schedule", ["execution_window_start", "execution_window_end"], unique=False)

    op.create_table(
        "template_governance_orchestration_control",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("control_status", sa.String(length=32), nullable=False),
        sa.Column("pause_reason", sa.Text(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("paused_by", sa.String(length=128), nullable=True),
        sa.Column("resumed_by", sa.String(length=128), nullable=True),
        sa.Column("canceled_by", sa.String(length=128), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", name="uq_template_governance_orchestration_control_plan_id"),
    )
    op.create_index("ix_template_governance_orchestration_control_status", "template_governance_orchestration_control", ["control_status"], unique=False)

    op.create_table(
        "template_governance_step_cooldown",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("step_id", sa.String(length=36), nullable=False),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_eligible_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cooldown_status", sa.String(length=32), nullable=False, server_default="ready"),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("step_id", name="uq_template_governance_step_cooldown_step_id"),
    )
    op.create_index("ix_template_governance_step_cooldown_next_eligible_run_at", "template_governance_step_cooldown", ["next_eligible_run_at"], unique=False)
    op.create_index("ix_template_governance_step_cooldown_status", "template_governance_step_cooldown", ["cooldown_status"], unique=False)

    op.create_table(
        "template_governance_post_plan_evaluation",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("outcome_label", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("before_metrics_json", sa.JSON(), nullable=True),
        sa.Column("after_metrics_json", sa.JSON(), nullable=True),
        sa.Column("deltas_json", sa.JSON(), nullable=True),
        sa.Column("evaluation_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", name="uq_template_governance_post_plan_evaluation_plan_id"),
    )
    op.create_index("ix_template_governance_post_plan_evaluation_outcome_label", "template_governance_post_plan_evaluation", ["outcome_label"], unique=False)
    op.create_index("ix_template_governance_post_plan_evaluation_status", "template_governance_post_plan_evaluation", ["status"], unique=False)

    op.create_table(
        "template_governance_policy_promotion_path",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("path_type", sa.String(length=32), nullable=False, server_default="hold"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="recommended"),
        sa.Column("confidence_delta", sa.Float(), nullable=False, server_default="0"),
        sa.Column("approval_requirement_delta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cooldown_delta_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recommendation_reason", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", name="uq_template_governance_policy_promotion_path_plan_id"),
    )
    op.create_index("ix_template_governance_policy_promotion_path_status", "template_governance_policy_promotion_path", ["status"], unique=False)
    op.create_index("ix_template_governance_policy_promotion_path_path_type", "template_governance_policy_promotion_path", ["path_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_template_governance_policy_promotion_path_path_type", table_name="template_governance_policy_promotion_path")
    op.drop_index("ix_template_governance_policy_promotion_path_status", table_name="template_governance_policy_promotion_path")
    op.drop_table("template_governance_policy_promotion_path")

    op.drop_index("ix_template_governance_post_plan_evaluation_status", table_name="template_governance_post_plan_evaluation")
    op.drop_index("ix_template_governance_post_plan_evaluation_outcome_label", table_name="template_governance_post_plan_evaluation")
    op.drop_table("template_governance_post_plan_evaluation")

    op.drop_index("ix_template_governance_step_cooldown_status", table_name="template_governance_step_cooldown")
    op.drop_index("ix_template_governance_step_cooldown_next_eligible_run_at", table_name="template_governance_step_cooldown")
    op.drop_table("template_governance_step_cooldown")

    op.drop_index("ix_template_governance_orchestration_control_status", table_name="template_governance_orchestration_control")
    op.drop_table("template_governance_orchestration_control")

    op.drop_index("ix_template_governance_schedule_window_start_end", table_name="template_governance_schedule")
    op.drop_index("ix_template_governance_schedule_scheduled_at", table_name="template_governance_schedule")
    op.drop_index("ix_template_governance_schedule_status", table_name="template_governance_schedule")
    op.drop_table("template_governance_schedule")
