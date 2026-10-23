"""Step 5.4: authenticated committed-turn evaluation orchestration.

Internal integration boundary. Caller must supply a resolver backed by its authenticated
repository/session service. No database, HTTP endpoint, persistence or network access
is implemented here. In-memory idempotency is per process only.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from threading import RLock
from typing import Callable
from uuid import UUID

from app.services.conversational_evidence import (
    ConversationalEvidence, ConversationalAssessmentDraft, ConversationalEvidenceError,
)
from app.services.controlled_conversational_evaluator import (
    EvaluationRequest, evaluate_conversation,
)


class TurnAssessmentError(ValueError):
    """Safe, content-independent contract error."""


@dataclass(frozen=True)
class CommittedTurnSnapshot:
    """Trusted ORM-to-domain projection made by the application's repository.

    The repository MUST verify the user/session ownership and state, and MUST NOT
    construct this from untrusted client payload alone. `text` is the exact committed
    learner text, not the assistant's response or a newly submitted replacement.
    """
    user_id: UUID
    practice_session_id: UUID
    conversation_turn_id: UUID
    client_request_id: UUID
    locale: str
    context: str
    scenario: str
    text: str
    origin: str
    stt_original_available: bool
    committed: bool
    learner_turn: bool


@dataclass(frozen=True)
class TurnAssessmentResult:
    turn_id: UUID
    client_request_id: UUID
    assessment: ConversationalAssessmentDraft
    # Digest is a provenance marker, not a secret nor proof of authorization.
    text_sha256: str
    scenario_type: str
    evaluator_version: str


class ConversationTurnAssessmentService:
    """Serialize evaluations and suppress duplicate provider calls per instance.

    This is NOT a durable exactly-once guarantee. For multi-process production use,
    replace the cache/lock with a DB transaction, a unique idempotency key and an
    evaluation state machine, and do not hold a DB transaction over LLM IO.
    """

    def __init__(self, *, resolve_turn: Callable[[UUID, UUID, UUID], CommittedTurnSnapshot],
                 model_call: Callable[[EvaluationRequest], str | dict]):
        if not callable(resolve_turn) or not callable(model_call):
            raise TurnAssessmentError('Trusted resolver and evaluator provider required')
        self._resolve_turn = resolve_turn
        self._model_call = model_call
        self._lock = RLock()
        self._results: dict[tuple[UUID, UUID, UUID, UUID], tuple[tuple, TurnAssessmentResult]] = {}

    def assess(self, *, authenticated_user_id: UUID, practice_session_id: UUID,
               conversation_turn_id: UUID, client_request_id: UUID,
               scenario_type: str, evaluator_version: str) -> TurnAssessmentResult:
        """Assess a previously committed learner turn; never accept client text here.

        Caller obtains authenticated_user_id from verified auth middleware, never
        from request body. Resolver must enforce tenant/user/session isolation.
        """
        ids = (authenticated_user_id, practice_session_id, conversation_turn_id, client_request_id)
        if any(type(value) is not UUID for value in ids):
            raise TurnAssessmentError('Invalid identity reference')
        if type(scenario_type) is not str or not scenario_type.strip():
            raise TurnAssessmentError('Invalid scenario type')
        if type(evaluator_version) is not str or not evaluator_version.strip():
            raise TurnAssessmentError('Invalid evaluator version')

        with self._lock:
            try:
                turn = self._resolve_turn(authenticated_user_id, practice_session_id, conversation_turn_id)
            except Exception as exc:
                raise TurnAssessmentError('Turn resolution or authorization failed') from exc
            if type(turn) is not CommittedTurnSnapshot or (
                turn.user_id != authenticated_user_id or
                turn.practice_session_id != practice_session_id or
                turn.conversation_turn_id != conversation_turn_id or
                turn.client_request_id != client_request_id or
                type(turn.committed) is not bool or not turn.committed or
                type(turn.learner_turn) is not bool or not turn.learner_turn
            ):
                raise TurnAssessmentError('Turn identity, ownership or state mismatch')

            try:
                evidence = ConversationalEvidence(
                    user_id=turn.user_id, practice_session_id=turn.practice_session_id,
                    conversation_turn_id=turn.conversation_turn_id,
                    client_request_id=turn.client_request_id, locale=turn.locale,
                    context=turn.context, scenario=turn.scenario, text=turn.text,
                    origin=turn.origin, authorized_turn=True,
                    stt_original_available=turn.stt_original_available,
                )
            except (ConversationalEvidenceError, ValueError, TypeError) as exc:
                raise TurnAssessmentError('Committed turn fails evidence contract') from exc

            text_digest = sha256(evidence.text.encode('utf-8')).hexdigest()
            # Includes all content relevant to the evaluation to catch changed turns
            # on retries. Deliberately does not store plaintext in the cache key.
            fingerprint = (
                text_digest, evidence.locale, evidence.context, evidence.scenario,
                evidence.origin, evidence.stt_original_available, scenario_type,
                evaluator_version,
            )
            existing = self._results.get(ids)
            if existing is not None:
                if existing[0] != fingerprint:
                    raise TurnAssessmentError('Idempotency conflict: turn evidence changed')
                return existing[1]

            # No result is cached for provider failure: retries are allowed.
            assessment = evaluate_conversation(
                evidence, scenario_type=scenario_type,
                evaluator_version=evaluator_version, model_call=self._model_call,
            )
            result = TurnAssessmentResult(
                turn_id=turn.conversation_turn_id, client_request_id=turn.client_request_id,
                assessment=assessment, text_sha256=text_digest,
                scenario_type=scenario_type, evaluator_version=evaluator_version,
            )
            self._results[ids] = (fingerprint, result)
            return result
