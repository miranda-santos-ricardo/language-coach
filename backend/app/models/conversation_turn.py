import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.language_feedback import LanguageFeedback
    from app.models.practice_session import PracticeSession


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"
    __table_args__ = (
        UniqueConstraint("practice_session_id", "turn_index", name="uq_conversation_turns_session_index"),
        UniqueConstraint("practice_session_id", "client_request_id", name="uq_conversation_turns_session_request"),
        CheckConstraint("turn_index > 0", name="turn_index_positive"),
        CheckConstraint("input_modality IN ('text', 'voice')", name="input_modality_valid"),
        CheckConstraint("length(trim(learner_text)) > 0", name="learner_text_not_blank"),
        CheckConstraint("length(trim(coach_response)) > 0", name="coach_response_not_blank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("practice_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    client_request_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    input_modality: Mapped[str] = mapped_column(String(10), nullable=False)
    learner_text: Mapped[str] = mapped_column(Text, nullable=False)
    coach_response: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    practice_session: Mapped["PracticeSession"] = relationship(back_populates="conversation_turns")
    feedback: Mapped["LanguageFeedback"] = relationship(
        back_populates="conversation_turn", uselist=False, cascade="all, delete-orphan", single_parent=True
    )
