"""Step 5.4b.7: opt-in authorized HTTP endpoint with durable assessment replay.

Must not be mounted without a host-supplied REAL Bearer verifier and an independent
SQLAlchemy session factory, whose schema has been migrated to c5202602.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.api.conversation_assessment import AssessmentInput
from app.api.conversation_assessment_auth import VerifiedIdentity, make_authenticated_identity_dependency
from app.services.conversation_turn_assessment import (
    ConversationTurnAssessmentService, TurnAssessmentError,
)
from app.services.controlled_conversational_evaluator import EvaluatorFailure
from app.services.conversational_evidence import ConversationalEvidence, ConversationalEvidenceError
from app.services.persistent_assessment_idempotency import (
    PersistentAssessmentLedger, AssessmentBusy, AssessmentConflict, evidence_fingerprint,
)
from app.services.sqlalchemy_turn_resolver import make_sqlalchemy_turn_resolver


class PersistentAssessmentSetupError(ValueError):
    pass


def install_persistent_assessment_endpoint(
    app: FastAPI, *, enabled: bool = False,
    verify_bearer_token: Callable[[str], VerifiedIdentity] | None = None,
    context_from_session: Callable | None = None,
    model_call: Callable | None = None,
    session_dependency: Callable | None = None,
    ledger_session_factory: Callable[[], Session] | None = None,
    scenario_type: str = 'general',
    evaluator_version: str = 'communication-rubric-v1',
) -> bool:
    """Explicit opt-in. Ledger sessions must be independent of request DB sessions.

    The host is responsible for verifying actual token crypto, rate limiting,
    provider timeouts, privacy/retention, and DB schema/migration deployment.
    """
    if not isinstance(app, FastAPI) or type(enabled) is not bool:
        raise PersistentAssessmentSetupError('Explicit FastAPI enablement required')
    if not enabled:
        return False
    if not all(callable(v) for v in (
        verify_bearer_token, context_from_session, model_call,
        session_dependency, ledger_session_factory,
    )):
        raise PersistentAssessmentSetupError('Verified identity, context, provider, DB and ledger factory required')
    if getattr(app.state, '_conversation_assessment_installed', False):
        raise PersistentAssessmentSetupError('Assessment route already installed')
    if not isinstance(scenario_type, str) or not scenario_type.strip():
        raise PersistentAssessmentSetupError('Scenario required')
    if not isinstance(evaluator_version, str) or not (0 < len(evaluator_version) <= 120):
        raise PersistentAssessmentSetupError('Evaluator version required')

    identity_dependency = make_authenticated_identity_dependency(verify_bearer_token)
    ledger = PersistentAssessmentLedger(ledger_session_factory)
    router = APIRouter(tags=['conversation-assessment'])

    @router.post('/practice-sessions/{practice_session_id}/turns/{turn_id}/assessment')
    def assess(
        practice_session_id: UUID,
        turn_id: UUID,
        payload: AssessmentInput,
        authenticated_user_id: UUID = Depends(identity_dependency),
        db: Session = Depends(session_dependency),
    ) -> dict:
        if type(authenticated_user_id) is not UUID or not isinstance(db, Session):
            raise HTTPException(status_code=503, detail='Assessment unavailable')
        resolver = make_sqlalchemy_turn_resolver(db, context_from_session=context_from_session)
        try:
            # Re-authorize the committed turn on EVERY attempt, including cached replay.
            turn = resolver(authenticated_user_id, practice_session_id, turn_id)
            if (turn.user_id != authenticated_user_id or turn.practice_session_id != practice_session_id
                    or turn.conversation_turn_id != turn_id or turn.client_request_id != payload.client_request_id
                    or not turn.committed or not turn.learner_turn):
                raise TurnAssessmentError('Committed turn identity mismatch')
            evidence = ConversationalEvidence(
                user_id=turn.user_id, practice_session_id=turn.practice_session_id,
                conversation_turn_id=turn.conversation_turn_id,
                client_request_id=turn.client_request_id, locale=turn.locale,
                context=turn.context, scenario=turn.scenario, text=turn.text,
                origin=turn.origin, authorized_turn=True,
                stt_original_available=turn.stt_original_available,
            )
        except (TurnAssessmentError, ConversationalEvidenceError):
            raise HTTPException(status_code=404, detail='Assessment unavailable') from None
        except Exception:
            raise HTTPException(status_code=503, detail='Assessment unavailable') from None

        digest = evidence_fingerprint(
            text=evidence.text, locale=evidence.locale, context=evidence.context,
            scenario=evidence.scenario, origin=evidence.origin,
            scenario_type=scenario_type, evaluator_version=evaluator_version,
            stt_original_available=evidence.stt_original_available,
        )

        def evaluate_once():
            # Existing service verifies the repository boundary again before executing.
            service = ConversationTurnAssessmentService(resolve_turn=resolver, model_call=model_call)
            result = service.assess(
                authenticated_user_id=authenticated_user_id,
                practice_session_id=practice_session_id, conversation_turn_id=turn_id,
                client_request_id=payload.client_request_id,
                scenario_type=scenario_type, evaluator_version=evaluator_version,
            )
            return {
                'turn_id': str(result.turn_id),
                'client_request_id': str(result.client_request_id),
                'text_sha256': result.text_sha256,
                'scenario_type': result.scenario_type,
                'evaluator_version': result.evaluator_version,
                'assessment': asdict(result.assessment),
            }

        try:
            outcome = ledger.execute(
                user_id=authenticated_user_id, practice_session_id=practice_session_id,
                turn_id=turn_id, client_request_id=payload.client_request_id,
                evaluator_version=evaluator_version, fingerprint=digest,
                evaluate=evaluate_once,
            )
        except AssessmentConflict:
            raise HTTPException(status_code=409, detail='Assessment evidence changed') from None
        except AssessmentBusy:
            # Can mean PROCESSING OR FAILED. No automatic retry in either case.
            raise HTTPException(status_code=409, detail='Assessment execution unavailable; reconciliation required') from None
        except (TurnAssessmentError, ConversationalEvidenceError, EvaluatorFailure):
            raise HTTPException(status_code=503, detail='Assessment unavailable') from None
        except Exception:
            raise HTTPException(status_code=503, detail='Assessment unavailable') from None
        return {**outcome.result, 'execution_id': str(outcome.execution_id), 'execution_status': outcome.status}

    app.include_router(router)
    app.state._conversation_assessment_installed = True
    return True
