"""Phase 7 Step 5.4a: fail-closed repository-to-domain bridge.

Requires real, authenticated repository queries; DOES NOT implement ORM queries.
Never create snapshots from request JSON. No raw learner text in errors/logs.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from uuid import UUID
from app.services.conversation_turn_assessment import CommittedTurnSnapshot, TurnAssessmentError


@dataclass(frozen=True)
class AuthorizedSessionRow:
    id: UUID
    user_id: UUID
    is_accessible: bool


@dataclass(frozen=True)
class PersistedLearnerTurnRow:
    id: UUID
    practice_session_id: UUID
    user_id: UUID
    client_request_id: UUID
    locale: str
    context: str
    scenario: str
    text: str
    origin: str
    stt_original_available: bool
    committed: bool
    learner_turn: bool


class AuthorizedConversationRepository:
    """Strict adapter over application-owned repository reads.

    fetch_session(user_id, session_id) MUST enforce authenticated ownership in
    the database query itself and return None for missing/cross-user sessions.
    fetch_turn(user_id, session_id, turn_id) MUST enforce ownership and linkage
    in the database query itself, not filter a globally fetched record afterward.
    Both reads should use a consistent transaction/snapshot to avoid TOCTOU.
    """
    def __init__(self, *, fetch_session: Callable, fetch_turn: Callable):
        if not callable(fetch_session) or not callable(fetch_turn):
            raise TurnAssessmentError('Authorized repository functions required')
        self._fetch_session = fetch_session
        self._fetch_turn = fetch_turn

    def resolve_turn(self, authenticated_user_id: UUID, practice_session_id: UUID,
                     conversation_turn_id: UUID) -> CommittedTurnSnapshot:
        if any(type(x) is not UUID for x in (authenticated_user_id, practice_session_id, conversation_turn_id)):
            raise TurnAssessmentError('Invalid identity reference')
        try:
            session = self._fetch_session(authenticated_user_id, practice_session_id)
            if type(session) is not AuthorizedSessionRow or (
                session.id != practice_session_id or
                session.user_id != authenticated_user_id or
                session.is_accessible is not True
            ):
                raise TurnAssessmentError('Session unavailable')
            turn = self._fetch_turn(authenticated_user_id, practice_session_id, conversation_turn_id)
            if type(turn) is not PersistedLearnerTurnRow or (
                turn.id != conversation_turn_id or
                turn.practice_session_id != practice_session_id or
                turn.user_id != authenticated_user_id or
                turn.committed is not True or turn.learner_turn is not True
            ):
                raise TurnAssessmentError('Turn unavailable')
            if any(type(x) is not UUID for x in (turn.client_request_id,)):
                raise TurnAssessmentError('Invalid committed request identity')
            if type(turn.text) is not str or not turn.text.strip():
                raise TurnAssessmentError('Committed turn contains no text')
            if type(turn.stt_original_available) is not bool:
                raise TurnAssessmentError('Invalid provenance flag')
            return CommittedTurnSnapshot(
                user_id=turn.user_id, practice_session_id=turn.practice_session_id,
                conversation_turn_id=turn.id, client_request_id=turn.client_request_id,
                locale=turn.locale, context=turn.context, scenario=turn.scenario,
                text=turn.text, origin=turn.origin,
                stt_original_available=turn.stt_original_available,
                committed=True, learner_turn=True,
            )
        except TurnAssessmentError:
            raise
        except Exception as exc:
            raise TurnAssessmentError('Authorized repository lookup failed') from exc
