"""backfill provider_status_raw from status

Revision ID: 20260410_0006
Revises: 20260410_0005
Create Date: 2026-04-10 10:10:00
"""

from __future__ import annotations

from alembic import op


revision = "20260410_0006"
down_revision = "20260410_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE render_scene_tasks
        SET provider_status_raw = status
        WHERE provider_status_raw IS NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE render_scene_tasks
        SET provider_status_raw = NULL
        WHERE provider_status_raw = status
        """
    )