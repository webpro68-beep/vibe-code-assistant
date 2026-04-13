"""add autopilot execution state

Revision ID: 20260411_0015
Revises: 20260411_0014
Create Date: 2026-04-11 00:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260411_0015"
down_revision = "20260411_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "autopilot_execution_states",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("decision_type", sa.String(length=64), nullable=False),
        sa.Column("recommendation_key", sa.String(length=128), nullable=True),
        sa.Column("last_status", sa.String(length=32), nullable=False),
        sa.Column("last_reason", sa.Text(), nullable=True),
        sa.Column("cooldown_until", sa.DateTime(), nullable=True),
        sa.Column("suppression_until", sa.DateTime(), nullable=True),
        sa.Column("last_executed_at", sa.DateTime(), nullable=True),
        sa.Column("last_evaluated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_autopilot_execution_states")),
    )
    op.create_index(op.f("ix_autopilot_execution_states_decision_type"), "autopilot_execution_states", ["decision_type"], unique=False)
    op.create_index(op.f("ix_autopilot_execution_states_recommendation_key"), "autopilot_execution_states", ["recommendation_key"], unique=False)
    op.create_index(op.f("ix_autopilot_execution_states_last_status"), "autopilot_execution_states", ["last_status"], unique=False)
    op.create_index(op.f("ix_autopilot_execution_states_cooldown_until"), "autopilot_execution_states", ["cooldown_until"], unique=False)
    op.create_index(op.f("ix_autopilot_execution_states_suppression_until"), "autopilot_execution_states", ["suppression_until"], unique=False)
    op.create_index(op.f("ix_autopilot_execution_states_last_executed_at"), "autopilot_execution_states", ["last_executed_at"], unique=False)
    op.create_index(op.f("ix_autopilot_execution_states_last_evaluated_at"), "autopilot_execution_states", ["last_evaluated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_autopilot_execution_states_last_evaluated_at"), table_name="autopilot_execution_states")
    op.drop_index(op.f("ix_autopilot_execution_states_last_executed_at"), table_name="autopilot_execution_states")
    op.drop_index(op.f("ix_autopilot_execution_states_suppression_until"), table_name="autopilot_execution_states")
    op.drop_index(op.f("ix_autopilot_execution_states_cooldown_until"), table_name="autopilot_execution_states")
    op.drop_index(op.f("ix_autopilot_execution_states_last_status"), table_name="autopilot_execution_states")
    op.drop_index(op.f("ix_autopilot_execution_states_recommendation_key"), table_name="autopilot_execution_states")
    op.drop_index(op.f("ix_autopilot_execution_states_decision_type"), table_name="autopilot_execution_states")
    op.drop_table("autopilot_execution_states")
