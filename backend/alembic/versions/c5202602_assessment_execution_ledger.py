"""Add persistent conversational assessment execution ledger.

Revision ID: c5202602
Revises: c5202601
"""
from alembic import op
import sqlalchemy as sa

revision = 'c5202602'
down_revision = 'c5202601'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'conversation_assessment_executions',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('practice_session_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('turn_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('client_request_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('evaluator_version', sa.String(length=120), nullable=False),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('result_json', sa.JSON(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id','practice_session_id','turn_id','client_request_id','evaluator_version', name='uq_assessment_execution_key'),
        sa.CheckConstraint("status IN ('PROCESSING','COMPLETED','FAILED')", name='ck_assessment_execution_status'),
    )
    op.create_index('ix_assessment_execution_user_updated','conversation_assessment_executions',['user_id','updated_at'])


def downgrade():
    op.drop_index('ix_assessment_execution_user_updated', table_name='conversation_assessment_executions')
    op.drop_table('conversation_assessment_executions')
