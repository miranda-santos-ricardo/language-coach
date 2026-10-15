"""Read authoritative language coaching context from existing persistence models."""
from dataclasses import dataclass
import uuid

from sqlalchemy.orm import Session

from app.models import SessionStatus
from app.repositories.language_profile import LanguageProfileRepository
from app.repositories.practice_session import PracticeSessionRepository
from app.repositories.conversation_turn import ConversationTurnRepository
from app.services.llm import LLMMessage


class ConversationContextNotFoundError(ValueError):
    """Requested user/profile/session chain does not exist."""


class ConversationSessionInactiveError(ValueError):
    """Conversation cannot be continued in this session."""


@dataclass(frozen=True)
class ConversationContext:
    language_variant: str
    language_name: str
    current_cefr: str
    target_cefr: str | None
    training_mode: str
    communication_register: str
    scenario_key: str | None
    recent_messages: tuple[LLMMessage, ...]


class ConversationContextResolver:
    def __init__(self, *, history_turn_limit: int = 10) -> None:
        if not 0 <= history_turn_limit <= 30:
            raise ValueError("history_turn_limit must be between 0 and 30")
        self.history_turn_limit = history_turn_limit

    def resolve(self, *, session: Session, user_id: uuid.UUID, profile_id: uuid.UUID,
                practice_session_id: uuid.UUID) -> ConversationContext:
        profile = LanguageProfileRepository.get_owned(session, user_id, profile_id)
        if profile is None:
            raise ConversationContextNotFoundError("Language profile or session not found")
        practice = PracticeSessionRepository.get_owned(session, profile.id, practice_session_id)
        if practice is None:
            raise ConversationContextNotFoundError("Language profile or session not found")
        if practice.status != SessionStatus.ACTIVE:
            raise ConversationSessionInactiveError("Practice session is not active")

        # May be lazy-loaded; all values are taken from persisted entities.
        variant = profile.language_variant
        register = practice.communication_register
        if variant is None or register is None or not variant.code or not register.code:
            raise ConversationContextNotFoundError("Incomplete session reference data")
        history: list[LLMMessage] = []
        if self.history_turn_limit:
            # Repository paginates in ascending order; load only the final N turns.
            from sqlalchemy import func, select
            from app.models import ConversationTurn
            count = session.scalar(select(func.count(ConversationTurn.id)).where(
                ConversationTurn.practice_session_id == practice.id)) or 0
            turns = ConversationTurnRepository.list_owned(
                session, user_id, profile_id, practice_session_id,
                limit=self.history_turn_limit, offset=max(0, count - self.history_turn_limit))
            for turn in turns:
                history.append(LLMMessage(role="user", content=turn.learner_text))
                history.append(LLMMessage(role="assistant", content=turn.coach_response))
        return ConversationContext(
            language_variant=variant.code,
            language_name=variant.language.name,
            current_cefr=practice.profile_cefr_snapshot.value,
            target_cefr=practice.target_cefr.value if practice.target_cefr is not None else None,
            training_mode=practice.training_mode.value,
            communication_register=register.code,
            scenario_key=practice.scenario_key,
            recent_messages=tuple(history),
        )
