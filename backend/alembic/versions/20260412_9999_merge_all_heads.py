"""merge all heads 20260412

Revision ID: 20260412_9999
Revises: 20260410_000002, 20260410_0007, 20260410_0012, 20260412_0025
Create Date: 2026-04-12 20:10:00.000000
"""

revision = "20260412_9999"
down_revision = (
    "20260410_000002",
    "20260410_0007",
    "20260410_0012",
    "20260412_0025",
)
branch_labels = None
depends_on = None


def upgrade():
    # IMPORTANT: no-op merge
    pass


def downgrade():
    pass
