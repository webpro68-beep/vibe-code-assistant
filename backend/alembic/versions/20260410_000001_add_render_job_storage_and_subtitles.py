"""add render job storage and subtitles

Revision ID: 20260410_000001
Revises:
Create Date: 2026-04-10 20:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260410_000001"
down_revision = "20260408_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("render_jobs", sa.Column("storage_key", sa.Text(), nullable=True))
    op.add_column("render_jobs", sa.Column("thumbnail_url", sa.Text(), nullable=True))
    op.add_column("render_jobs", sa.Column("subtitle_segments", sa.JSON(), nullable=True))
    op.add_column("render_jobs", sa.Column("final_timeline", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("render_jobs", "final_timeline")
    op.drop_column("render_jobs", "subtitle_segments")
    op.drop_column("render_jobs", "thumbnail_url")
    op.drop_column("render_jobs", "storage_key")