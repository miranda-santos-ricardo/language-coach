"""Immutable-by-application operator reconciliation evidence.

Revision ID: c5202603
Revises: c5202602
"""
from alembic import op
import sqlalchemy as sa

revision = 'c5202603'
down_revision = 'c5202602'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'conversation_assessment_reconciliation_events',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('execution_id', sa.Uuid(as_uuid=True), sa.ForeignKey('conversation_assessment_executions.id'), nullable=False),
        sa.Column('operator_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('previous_status', sa.String(length=20), nullable=False),
        sa.Column('new_status', sa.String(length=20), nullable=False),
        sa.Column('reason_code', sa.String(length=60), nullable=False),
        sa.Column('ticket_reference', sa.String(length=120), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_assessment_reconciliation_execution', 'conversation_assessment_reconciliation_events', ['execution_id', 'occurred_at'])


def downgrade():
    op.drop_index('ix_assessment_reconciliation_execution', table_name='conversation_assessment_reconciliation_events')
    op.drop_table('conversation_assessment_reconciliation_events')
