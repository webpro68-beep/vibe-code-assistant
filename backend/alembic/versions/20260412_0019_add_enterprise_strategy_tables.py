"""add enterprise strategy tables

Revision ID: 20260412_0019
Revises: 20260412_0018
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260412_0019"
down_revision = "20260412_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "enterprise_strategy_signals",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("project_id", sa.String(length=64)),
        sa.Column("customer_tier", sa.String(length=32)),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "objective_profiles",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("objective_stack_json", sa.Text(), nullable=False),
        sa.Column("directive_summary_json", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ttl_minutes", sa.Integer()),
    )
    op.create_table(
        "contract_sla_profiles",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("customer_tier", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=64)),
        sa.Column("target_latency_minutes", sa.Integer()),
        sa.Column("target_success_rate_bps", sa.Integer()),
        sa.Column("penalty_weight", sa.Integer(), nullable=False, server_default="50"),
    )
    op.create_table(
        "campaign_windows",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("campaign_type", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64)),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
    )
    op.create_table(
        "roadmap_priorities",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("roadmap_key", sa.String(length=128), nullable=False, unique=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("project_id", sa.String(length=64)),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("notes", sa.Text()),
    )
    op.create_table(
        "portfolio_allocation_plans",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("plan_name", sa.String(length=255), nullable=False),
        sa.Column("allocation_json", sa.Text(), nullable=False),
        sa.Column("reserve_capacity_percent", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "business_outcome_snapshots",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("revenue_index", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("sla_attainment_bps", sa.Integer(), nullable=False, server_default="9900"),
        sa.Column("throughput_index", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("margin_index", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "strategy_directives",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("directive_type", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False, server_default="global"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("ttl_minutes", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    for table in [
        "strategy_directives",
        "business_outcome_snapshots",
        "portfolio_allocation_plans",
        "roadmap_priorities",
        "campaign_windows",
        "contract_sla_profiles",
        "objective_profiles",
        "enterprise_strategy_signals",
    ]:
        op.drop_table(table)
