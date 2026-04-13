"""enforce provider_status_raw not null

Revision ID: 20260410_0007
Revises: 20260410_0006
Create Date: 2026-04-10 10:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260410_0007"
down_revision = "20260410_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "render_scene_tasks",
        "provider_status_raw",
        existing_type=sa.String(length=128),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "render_scene_tasks",
        "provider_status_raw",
        existing_type=sa.String(length=128),
        nullable=True,
    )