"""add render timeline and health snapshot

Revision ID: 20260410_0009
Revises: 20260410_0008
"""
from alembic import op
import sqlalchemy as sa

revision = "20260410_0009"
down_revision = "20260410_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('render_jobs', sa.Column('health_status', sa.String(length=32), nullable=True))
    op.add_column('render_jobs', sa.Column('health_reason', sa.Text(), nullable=True))
    op.add_column('render_jobs', sa.Column('processing_scene_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('render_jobs', sa.Column('failed_scene_count_snapshot', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('render_jobs', sa.Column('stalled_scene_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('render_jobs', sa.Column('degraded_scene_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('render_jobs', sa.Column('active_scene_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('render_jobs', sa.Column('last_event_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('render_jobs', sa.Column('last_health_transition_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_render_jobs_health_status'), 'render_jobs', ['health_status'], unique=False)

    op.add_column('render_scene_tasks', sa.Column('provider_status_observed_at', sa.DateTime(), nullable=True))
    op.add_column('render_scene_tasks', sa.Column('last_stalled_at', sa.DateTime(), nullable=True))

    op.create_table('render_timeline_events',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('scene_task_id', sa.String(length=64), nullable=True),
        sa.Column('scene_index', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=32), nullable=False),
        sa.Column('event_type', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('provider', sa.String(length=64), nullable=True),
        sa.Column('provider_status_raw', sa.String(length=128), nullable=True),
        sa.Column('provider_request_id', sa.String(length=255), nullable=True),
        sa.Column('provider_task_id', sa.String(length=255), nullable=True),
        sa.Column('provider_operation_name', sa.String(length=255), nullable=True),
        sa.Column('failure_code', sa.String(length=128), nullable=True),
        sa.Column('failure_category', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('signature_valid', sa.Boolean(), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=True),
        sa.Column('event_idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['render_jobs.id']),
        sa.ForeignKeyConstraint(['scene_task_id'], ['render_scene_tasks.id']),
    )
    for cols in [['job_id'],['scene_task_id'],['scene_index'],['source'],['event_type'],['status'],['provider'],['provider_task_id'],['provider_operation_name'],['event_idempotency_key'],['occurred_at']]:
        op.create_index(op.f('ix_render_timeline_events_' + '_'.join(cols)), 'render_timeline_events', cols, unique=False)


def downgrade() -> None:
    op.drop_table('render_timeline_events')
    op.drop_column('render_scene_tasks', 'last_stalled_at')
    op.drop_column('render_scene_tasks', 'provider_status_observed_at')
    op.drop_index(op.f('ix_render_jobs_health_status'), table_name='render_jobs')
    for c in ['last_health_transition_at','last_event_at','active_scene_count','degraded_scene_count','stalled_scene_count','failed_scene_count_snapshot','processing_scene_count','health_reason','health_status']:
        op.drop_column('render_jobs', c)
