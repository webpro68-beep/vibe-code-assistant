"""add control plane runtime tables

Revision ID: 20260411_0014
Revises: 20260411_0013
Create Date: 2026-04-11 00:14:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260411_0014"
down_revision = "20260411_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worker_concurrency_overrides",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("queue_name", sa.String(length=64), nullable=False),
        sa.Column("dispatch_batch_limit", sa.Integer(), nullable=False),
        sa.Column("poll_countdown_seconds", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_worker_concurrency_overrides")),
        sa.UniqueConstraint("queue_name", name=op.f("uq_worker_concurrency_overrides_queue_name")),
    )
    op.create_index(op.f("ix_worker_concurrency_overrides_queue_name"), "worker_concurrency_overrides", ["queue_name"], unique=False)

    op.create_table(
        "provider_routing_overrides",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source_provider", sa.String(length=64), nullable=False),
        sa.Column("target_provider", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_routing_overrides")),
        sa.UniqueConstraint("source_provider", name=op.f("uq_provider_routing_overrides_source_provider")),
    )
    op.create_index(op.f("ix_provider_routing_overrides_source_provider"), "provider_routing_overrides", ["source_provider"], unique=False)
    op.create_index(op.f("ix_provider_routing_overrides_target_provider"), "provider_routing_overrides", ["target_provider"], unique=False)
    op.create_index(op.f("ix_provider_routing_overrides_active"), "provider_routing_overrides", ["active"], unique=False)
    op.create_index(op.f("ix_provider_routing_overrides_expires_at"), "provider_routing_overrides", ["expires_at"], unique=False)

    op.create_table(
        "release_gate_states",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("gate_name", sa.String(length=64), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("last_decision_type", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_release_gate_states")),
        sa.UniqueConstraint("gate_name", name=op.f("uq_release_gate_states_gate_name")),
    )
    op.create_index(op.f("ix_release_gate_states_gate_name"), "release_gate_states", ["gate_name"], unique=False)
    op.create_index(op.f("ix_release_gate_states_blocked"), "release_gate_states", ["blocked"], unique=False)

    op.create_table(
        "decision_execution_audit_logs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("decision_type", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("execution_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("action_payload_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("policy_version", sa.String(length=64), nullable=True),
        sa.Column("recommendation_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_execution_audit_logs")),
    )
    op.create_index(op.f("ix_decision_execution_audit_logs_decision_type"), "decision_execution_audit_logs", ["decision_type"], unique=False)
    op.create_index(op.f("ix_decision_execution_audit_logs_actor"), "decision_execution_audit_logs", ["actor"], unique=False)
    op.create_index(op.f("ix_decision_execution_audit_logs_execution_status"), "decision_execution_audit_logs", ["execution_status"], unique=False)
    op.create_index(op.f("ix_decision_execution_audit_logs_recommendation_key"), "decision_execution_audit_logs", ["recommendation_key"], unique=False)
    op.create_index(op.f("ix_decision_execution_audit_logs_created_at"), "decision_execution_audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_decision_execution_audit_logs_created_at"), table_name="decision_execution_audit_logs")
    op.drop_index(op.f("ix_decision_execution_audit_logs_recommendation_key"), table_name="decision_execution_audit_logs")
    op.drop_index(op.f("ix_decision_execution_audit_logs_execution_status"), table_name="decision_execution_audit_logs")
    op.drop_index(op.f("ix_decision_execution_audit_logs_actor"), table_name="decision_execution_audit_logs")
    op.drop_index(op.f("ix_decision_execution_audit_logs_decision_type"), table_name="decision_execution_audit_logs")
    op.drop_table("decision_execution_audit_logs")

    op.drop_index(op.f("ix_release_gate_states_blocked"), table_name="release_gate_states")
    op.drop_index(op.f("ix_release_gate_states_gate_name"), table_name="release_gate_states")
    op.drop_table("release_gate_states")

    op.drop_index(op.f("ix_provider_routing_overrides_expires_at"), table_name="provider_routing_overrides")
    op.drop_index(op.f("ix_provider_routing_overrides_active"), table_name="provider_routing_overrides")
    op.drop_index(op.f("ix_provider_routing_overrides_target_provider"), table_name="provider_routing_overrides")
    op.drop_index(op.f("ix_provider_routing_overrides_source_provider"), table_name="provider_routing_overrides")
    op.drop_table("provider_routing_overrides")

    op.drop_index(op.f("ix_worker_concurrency_overrides_queue_name"), table_name="worker_concurrency_overrides")
    op.drop_table("worker_concurrency_overrides")
