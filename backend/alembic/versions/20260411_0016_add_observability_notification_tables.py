"""add observability notification tables

Revision ID: 20260411_0016
Revises: 20260411_0015
Create Date: 2026-04-11 00:16:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260411_0016"
down_revision = "20260411_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "global_kill_switches",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("switch_name", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_global_kill_switches")),
        sa.UniqueConstraint("switch_name", name=op.f("uq_global_kill_switches_switch_name")),
    )
    op.create_index(op.f("ix_global_kill_switches_switch_name"), "global_kill_switches", ["switch_name"], unique=False)
    op.create_index(op.f("ix_global_kill_switches_enabled"), "global_kill_switches", ["enabled"], unique=False)

    op.create_table(
        "notification_endpoints",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("channel_type", sa.String(length=32), nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("event_filter", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("secret", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_endpoints")),
        sa.UniqueConstraint("name", name=op.f("uq_notification_endpoints_name")),
    )
    op.create_index(op.f("ix_notification_endpoints_name"), "notification_endpoints", ["name"], unique=False)
    op.create_index(op.f("ix_notification_endpoints_channel_type"), "notification_endpoints", ["channel_type"], unique=False)
    op.create_index(op.f("ix_notification_endpoints_enabled"), "notification_endpoints", ["enabled"], unique=False)

    op.create_table(
        "notification_delivery_logs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("endpoint_name", sa.String(length=128), nullable=False),
        sa.Column("channel_type", sa.String(length=32), nullable=False),
        sa.Column("delivery_status", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_delivery_logs")),
    )
    op.create_index(op.f("ix_notification_delivery_logs_event_type"), "notification_delivery_logs", ["event_type"], unique=False)
    op.create_index(op.f("ix_notification_delivery_logs_endpoint_name"), "notification_delivery_logs", ["endpoint_name"], unique=False)
    op.create_index(op.f("ix_notification_delivery_logs_channel_type"), "notification_delivery_logs", ["channel_type"], unique=False)
    op.create_index(op.f("ix_notification_delivery_logs_delivery_status"), "notification_delivery_logs", ["delivery_status"], unique=False)
    op.create_index(op.f("ix_notification_delivery_logs_created_at"), "notification_delivery_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_delivery_logs_created_at"), table_name="notification_delivery_logs")
    op.drop_index(op.f("ix_notification_delivery_logs_delivery_status"), table_name="notification_delivery_logs")
    op.drop_index(op.f("ix_notification_delivery_logs_channel_type"), table_name="notification_delivery_logs")
    op.drop_index(op.f("ix_notification_delivery_logs_endpoint_name"), table_name="notification_delivery_logs")
    op.drop_index(op.f("ix_notification_delivery_logs_event_type"), table_name="notification_delivery_logs")
    op.drop_table("notification_delivery_logs")

    op.drop_index(op.f("ix_notification_endpoints_enabled"), table_name="notification_endpoints")
    op.drop_index(op.f("ix_notification_endpoints_channel_type"), table_name="notification_endpoints")
    op.drop_index(op.f("ix_notification_endpoints_name"), table_name="notification_endpoints")
    op.drop_table("notification_endpoints")

    op.drop_index(op.f("ix_global_kill_switches_enabled"), table_name="global_kill_switches")
    op.drop_index(op.f("ix_global_kill_switches_switch_name"), table_name="global_kill_switches")
    op.drop_table("global_kill_switches")
