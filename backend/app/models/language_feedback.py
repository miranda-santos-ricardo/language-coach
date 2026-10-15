import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, JSON, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation_turn import ConversationTurn


class LanguageFeedback(Base):
    __tablename__ = "language_feedback"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_turn_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conversation_turns.id", ondelete="CASCADE"),
        nullable=False, unique=True
    )
    overall_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    grammar_feedback: Mapped[dict] = mapped_column(JSON, nullable=False)
    vocabulary_feedback: Mapped[dict] = mapped_column(JSON, nullable=False)
    clarity_feedback: Mapped[dict] = mapped_column(JSON, nullable=False)
    naturalness_feedback: Mapped[dict] = mapped_column(JSON, nullable=False)
    register_feedback: Mapped[dict] = mapped_column(JSON, nullable=False)
    improved_version: Mapped[str] = mapped_column(Text, nullable=False)
    explanations: Mapped[list] = mapped_column(JSON, nullable=False)
    strengths: Mapped[list] = mapped_column(JSON, nullable=False)
    next_recommendation: Mapped[str] = mapped_column(Text, nullable=False)

    conversation_turn: Mapped["ConversationTurn"] = relationship(back_populates="feedback")
