import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import ConversationTurn, LanguageFeedback, LanguageProfile, PracticeSession


class ConversationTurnRepository:
    """Database operations only; caller owns transaction and commits atomically."""

    @staticmethod
    def add_with_feedback(session: Session, turn: ConversationTurn, feedback: LanguageFeedback) -> None:
        turn.feedback = feedback
        session.add(turn)
        # Flush will check both records together; service must commit/rollback.
        session.flush()

    @staticmethod
    def _owned_query(user_id: uuid.UUID, profile_id: uuid.UUID, session_id: uuid.UUID):
        return (
            select(ConversationTurn)
            .join(PracticeSession, ConversationTurn.practice_session_id == PracticeSession.id)
            .join(LanguageProfile, PracticeSession.language_profile_id == LanguageProfile.id)
            .where(LanguageProfile.user_id == user_id,
                   LanguageProfile.id == profile_id,
                   PracticeSession.id == session_id)
            .options(joinedload(ConversationTurn.feedback))
        )

    @classmethod
    def get_owned(cls, session: Session, user_id: uuid.UUID, profile_id: uuid.UUID,
                  session_id: uuid.UUID, turn_id: uuid.UUID) -> ConversationTurn | None:
        return session.scalar(cls._owned_query(user_id, profile_id, session_id).where(ConversationTurn.id == turn_id))

    @classmethod
    def get_by_request_id(cls, session: Session, user_id: uuid.UUID, profile_id: uuid.UUID,
                          session_id: uuid.UUID, request_id: uuid.UUID) -> ConversationTurn | None:
        return session.scalar(cls._owned_query(user_id, profile_id, session_id).where(ConversationTurn.client_request_id == request_id))

    @classmethod
    def list_owned(cls, session: Session, user_id: uuid.UUID, profile_id: uuid.UUID,
                   session_id: uuid.UUID, *, limit: int = 50, offset: int = 0) -> list[ConversationTurn]:
        if not (1 <= limit <= 100) or offset < 0:
            raise ValueError("Invalid pagination")
        query = (cls._owned_query(user_id, profile_id, session_id)
                 .order_by(ConversationTurn.turn_index.asc()).limit(limit).offset(offset))
        return list(session.scalars(query))
