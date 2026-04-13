
"""add render incident saved views

Revision ID: 20260410_0011
Revises: 20260410_0010
"""

from alembic import op
import sqlalchemy as sa

revision = "20260410_0011"
down_revision = "20260410_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "render_incident_saved_views",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("owner_actor", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("filters_json", sa.Text(), nullable=False, server_default='{}'),
        sa.Column("sort_key", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_render_incident_saved_views_owner_actor", "render_incident_saved_views", ["owner_actor"])
    op.create_index("ix_render_incident_saved_views_name", "render_incident_saved_views", ["name"])
    op.create_index("ix_render_incident_saved_views_is_shared", "render_incident_saved_views", ["is_shared"])


def downgrade() -> None:
    op.drop_index("ix_render_incident_saved_views_is_shared", table_name="render_incident_saved_views")
    op.drop_index("ix_render_incident_saved_views_name", table_name="render_incident_saved_views")
    op.drop_index("ix_render_incident_saved_views_owner_actor", table_name="render_incident_saved_views")
    op.drop_table("render_incident_saved_views")
