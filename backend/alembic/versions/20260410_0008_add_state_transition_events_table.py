"""add state_transition_events table

Revision ID: 20260410_0008
Revises: 20260408_0004
Create Date: 2026-04-10 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260410_0008"
down_revision = "20260408_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "state_transition_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("scene_task_id", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("old_state", sa.String(length=64), nullable=False),
        sa.Column("new_state", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_index(
        "ix_state_transition_events_entity_type_entity_id",
        "state_transition_events",
        ["entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_state_transition_events_job_id",
        "state_transition_events",
        ["job_id"],
        unique=False,
    )
    op.create_index(
        "ix_state_transition_events_scene_task_id",
        "state_transition_events",
        ["scene_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_state_transition_events_source",
        "state_transition_events",
        ["source"],
        unique=False,
    )
    op.create_index(
        "ix_state_transition_events_created_at",
        "state_transition_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_state_transition_events_created_at", table_name="state_transition_events")
    op.drop_index("ix_state_transition_events_source", table_name="state_transition_events")
    op.drop_index("ix_state_transition_events_scene_task_id", table_name="state_transition_events")
    op.drop_index("ix_state_transition_events_job_id", table_name="state_transition_events")
    op.drop_index("ix_state_transition_events_entity_type_entity_id", table_name="state_transition_events")
    op.drop_table("state_transition_events")