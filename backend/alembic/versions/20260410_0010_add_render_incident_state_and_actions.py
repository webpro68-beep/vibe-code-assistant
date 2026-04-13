"""add render incident state and actions

Revision ID: 20260410_0010
Revises: 20260410_0009
"""
from alembic import op
import sqlalchemy as sa

revision = "20260410_0010"
down_revision = "20260410_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('render_incident_states',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('incident_key', sa.String(length=255), nullable=False),
        sa.Column('job_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('incident_family', sa.String(length=64), nullable=False),
        sa.Column('current_event_id', sa.String(length=64), nullable=True),
        sa.Column('current_event_type', sa.String(length=64), nullable=True),
        sa.Column('current_severity_rank', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('last_transition_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='open'),
        sa.Column('acknowledged', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('acknowledged_by', sa.String(length=255), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('assigned_to', sa.String(length=255), nullable=True),
        sa.Column('assigned_by', sa.String(length=255), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('muted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('muted_until', sa.DateTime(), nullable=True),
        sa.Column('muted_by', sa.String(length=255), nullable=True),
        sa.Column('mute_reason', sa.Text(), nullable=True),
        sa.Column('suppressed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('suppression_reason', sa.String(length=64), nullable=True),
        sa.Column('reopen_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_reopened_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_render_incident_states_incident_key'), 'render_incident_states', ['incident_key'], unique=True)
    op.create_index(op.f('ix_render_incident_states_provider'), 'render_incident_states', ['provider'], unique=False)
    op.create_index(op.f('ix_render_incident_states_status'), 'render_incident_states', ['status'], unique=False)
    op.create_index(op.f('ix_render_incident_states_last_seen_at'), 'render_incident_states', ['last_seen_at'], unique=False)

    op.create_table('render_incident_actions',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('incident_key', sa.String(length=255), nullable=False),
        sa.Column('event_id', sa.String(length=64), nullable=True),
        sa.Column('job_id', sa.String(length=64), nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('actor', sa.String(length=255), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_render_incident_actions_incident_key'), 'render_incident_actions', ['incident_key'], unique=False)
    op.create_index(op.f('ix_render_incident_actions_action_type'), 'render_incident_actions', ['action_type'], unique=False)
    op.create_index(op.f('ix_render_incident_actions_actor'), 'render_incident_actions', ['actor'], unique=False)
    op.create_index(op.f('ix_render_incident_actions_created_at'), 'render_incident_actions', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('render_incident_actions')
    op.drop_table('render_incident_states')
