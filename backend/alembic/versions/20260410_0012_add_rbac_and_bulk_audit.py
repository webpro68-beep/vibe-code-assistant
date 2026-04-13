"""add rbac and bulk audit

Revision ID: 20260410_0012
Revises: 20260410_0011
"""

from alembic import op
import sqlalchemy as sa

revision = "20260410_0012"
down_revision = "20260410_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("render_incident_saved_views", sa.Column("share_scope", sa.String(length=32), nullable=False, server_default="private"))
    op.add_column("render_incident_saved_views", sa.Column("shared_team_id", sa.String(length=255), nullable=True))
    op.add_column("render_incident_saved_views", sa.Column("allowed_roles_json", sa.Text(), nullable=False, server_default="[]"))
    op.create_index("ix_render_incident_saved_views_share_scope", "render_incident_saved_views", ["share_scope"])
    op.create_index("ix_render_incident_saved_views_shared_team_id", "render_incident_saved_views", ["shared_team_id"])

    op.create_table(
        "render_operator_access_profiles",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("actor_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("team_id", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("scopes_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_render_operator_access_profiles_actor_id", "render_operator_access_profiles", ["actor_id"], unique=True)
    op.create_index("ix_render_operator_access_profiles_role", "render_operator_access_profiles", ["role"])
    op.create_index("ix_render_operator_access_profiles_team_id", "render_operator_access_profiles", ["team_id"])
    op.create_index("ix_render_operator_access_profiles_is_active", "render_operator_access_profiles", ["is_active"])

    op.create_table(
        "render_incident_bulk_action_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("actor_role", sa.String(length=64), nullable=False),
        sa.Column("actor_team_id", sa.String(length=255), nullable=True),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("filters_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("request_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("attempted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for col in ["action_type","actor","actor_team_id","mode","created_at"]:
        op.create_index(f"ix_render_incident_bulk_action_runs_{col}", "render_incident_bulk_action_runs", [col])

    op.create_table(
        "render_incident_bulk_action_items",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("incident_key", sa.String(length=255), nullable=False),
        sa.Column("ok", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for col in ["run_id","incident_key","created_at"]:
        op.create_index(f"ix_render_incident_bulk_action_items_{col}", "render_incident_bulk_action_items", [col])


def downgrade() -> None:
    op.drop_table("render_incident_bulk_action_items")
    op.drop_table("render_incident_bulk_action_runs")
    op.drop_table("render_operator_access_profiles")
    op.drop_index("ix_render_incident_saved_views_shared_team_id", table_name="render_incident_saved_views")
    op.drop_index("ix_render_incident_saved_views_share_scope", table_name="render_incident_saved_views")
    op.drop_column("render_incident_saved_views", "allowed_roles_json")
    op.drop_column("render_incident_saved_views", "shared_team_id")
    op.drop_column("render_incident_saved_views", "share_scope")
