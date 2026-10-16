"""Read-only access to persisted conversation turns, without LLM dependencies."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LanguageProfile, PracticeSession
from app.repositories.conversation_turn import ConversationTurnRepository
from app.services.conversation_context import ConversationContextNotFoundError


class ConversationReadService:
    """Validate the whole ownership chain even if there are no saved turns.

    Completed/abandoned sessions remain readable. No model calls or commits.
    """

    @staticmethod
    def _check_ownership(session: Session, user_id: uuid.UUID,
                         profile_id: uuid.UUID, practice_session_id: uuid.UUID) -> None:
        owned = session.scalar(
            select(PracticeSession.id)
            .join(LanguageProfile, PracticeSession.language_profile_id == LanguageProfile.id)
            .where(
                LanguageProfile.user_id == user_id,
                LanguageProfile.id == profile_id,
                PracticeSession.id == practice_session_id,
            )
        )
        if owned is None:
            raise ConversationContextNotFoundError("Conversation context not found")

    def list_turns(self, *, session: Session, user_id: uuid.UUID, profile_id: uuid.UUID,
                   practice_session_id: uuid.UUID, limit: int = 50, offset: int = 0):
        self._check_ownership(session, user_id, profile_id, practice_session_id)
        return ConversationTurnRepository.list_owned(
            session, user_id, profile_id, practice_session_id, limit=limit, offset=offset
        )

    def get_turn(self, *, session: Session, user_id: uuid.UUID, profile_id: uuid.UUID,
                 practice_session_id: uuid.UUID, turn_id: uuid.UUID):
        self._check_ownership(session, user_id, profile_id, practice_session_id)
        turn = ConversationTurnRepository.get_owned(
            session, user_id, profile_id, practice_session_id, turn_id
        )
        if turn is None:
            raise ConversationContextNotFoundError("Conversation turn not found")
        return turn
