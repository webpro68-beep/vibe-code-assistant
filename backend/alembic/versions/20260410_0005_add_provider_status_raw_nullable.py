"""add provider_status_raw nullable

Revision ID: 20260410_0005
Revises: 20260408_0004
Create Date: 2026-04-10 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260410_0005"
down_revision = "20260408_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "render_scene_tasks",
        sa.Column("provider_status_raw", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("render_scene_tasks", "provider_status_raw")