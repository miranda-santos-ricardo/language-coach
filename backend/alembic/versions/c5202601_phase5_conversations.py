"""Phase 5 conversation domain and structured feedback

Revision ID: c5202601
Revises: ba35d4c616d6
"""
from alembic import op
import sqlalchemy as sa

revision = "c5202601"
down_revision = "ba35d4c616d6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "conversation_turns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("practice_session_id", sa.Uuid(), sa.ForeignKey("practice_sessions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("client_request_id", sa.Uuid(), nullable=False),
        sa.Column("input_modality", sa.String(10), nullable=False),
        sa.Column("learner_text", sa.Text(), nullable=False),
        sa.Column("coach_response", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("practice_session_id", "turn_index", name="uq_conversation_turns_session_index"),
        sa.UniqueConstraint("practice_session_id", "client_request_id", name="uq_conversation_turns_session_request"),
        sa.CheckConstraint("turn_index > 0", name="ck_conversation_turns_turn_index_positive"),
        sa.CheckConstraint("input_modality IN ('text', 'voice')", name="ck_conversation_turns_input_modality_valid"),
        sa.CheckConstraint("length(trim(learner_text)) > 0", name="ck_conversation_turns_learner_text_not_blank"),
        sa.CheckConstraint("length(trim(coach_response)) > 0", name="ck_conversation_turns_coach_response_not_blank"),
    )
    op.create_index("ix_conversation_turns_practice_session_id", "conversation_turns", ["practice_session_id"])
    op.create_table(
        "language_feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_turn_id", sa.Uuid(), sa.ForeignKey("conversation_turns.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("overall_assessment", sa.Text(), nullable=False),
        sa.Column("grammar_feedback", sa.JSON(), nullable=False),
        sa.Column("vocabulary_feedback", sa.JSON(), nullable=False),
        sa.Column("clarity_feedback", sa.JSON(), nullable=False),
        sa.Column("naturalness_feedback", sa.JSON(), nullable=False),
        sa.Column("register_feedback", sa.JSON(), nullable=False),
        sa.Column("improved_version", sa.Text(), nullable=False),
        sa.Column("explanations", sa.JSON(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("next_recommendation", sa.Text(), nullable=False),
    )


def downgrade():
    op.drop_table("language_feedback")
    op.drop_index("ix_conversation_turns_practice_session_id", table_name="conversation_turns")
    op.drop_table("conversation_turns")
