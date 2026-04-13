from alembic import op
import sqlalchemy as sa

revision = "20260408_0004"
down_revision = "20260408_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_webhook_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=True),
        sa.Column("event_idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("scene_task_id", sa.String(length=64), nullable=True),
        sa.Column("provider_task_id", sa.String(length=255), nullable=True),
        sa.Column("provider_operation_name", sa.String(length=255), nullable=True),
        sa.Column("signature_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("headers_json", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("normalized_payload_json", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("event_idempotency_key", name="uq_provider_webhook_events_idem_key"),
    )

    op.create_index("ix_provider_webhook_events_provider", "provider_webhook_events", ["provider"])
    op.create_index("ix_provider_webhook_events_scene_task_id", "provider_webhook_events", ["scene_task_id"])
    op.create_index("ix_provider_webhook_events_provider_task_id", "provider_webhook_events", ["provider_task_id"])
    op.create_index("ix_provider_webhook_events_provider_operation_name", "provider_webhook_events", ["provider_operation_name"])


def downgrade() -> None:
    op.drop_index("ix_provider_webhook_events_provider_operation_name", table_name="provider_webhook_events")
    op.drop_index("ix_provider_webhook_events_provider_task_id", table_name="provider_webhook_events")
    op.drop_index("ix_provider_webhook_events_scene_task_id", table_name="provider_webhook_events")
    op.drop_index("ix_provider_webhook_events_provider", table_name="provider_webhook_events")
    op.drop_table("provider_webhook_events")