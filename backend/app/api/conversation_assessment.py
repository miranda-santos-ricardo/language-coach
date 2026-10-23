"""Phase 7 Step 5.4b.2: opt-in FastAPI route for committed-turn text review.

The hosting application must mount this router and supply authenticated identity,
request-scoped DB-backed resolver, and a configured evaluator service dependency.
No production OpenAI call, auto-registration, or persistence is introduced here.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Callable, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.services.conversation_turn_assessment import (
    ConversationTurnAssessmentService, TurnAssessmentError,
)
from app.services.controlled_conversational_evaluator import EvaluatorFailure


class AssessmentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    # Existing committed turn's request ID, NOT an arbitrary new one.
    client_request_id: UUID


# Important: all dependency callables must be supplied by the host application;
# never trust user_id supplied in path, query, headers or request body.
def create_conversation_assessment_router(
    *,
    get_authenticated_user_id: Callable[..., Any],
    get_assessment_service: Callable[..., Any],
    scenario_type: str = 'general',
    evaluator_version: str = 'communication-rubric-v1',
) -> APIRouter:
    if not callable(get_authenticated_user_id) or not callable(get_assessment_service):
        raise ValueError('Trusted authentication and service dependencies required')
    if not isinstance(scenario_type, str) or not scenario_type.strip():
        raise ValueError('Server-side scenario type required')
    if not isinstance(evaluator_version, str) or not evaluator_version.strip():
        raise ValueError('Server-side evaluator version required')

    router = APIRouter(tags=['conversation-assessment'])

    @router.post('/practice-sessions/{practice_session_id}/turns/{turn_id}/assessment',
                 status_code=status.HTTP_200_OK)
    def assess_committed_turn(
        practice_session_id: UUID,
        turn_id: UUID,
        payload: AssessmentInput,
        authenticated_user_id: UUID = Depends(get_authenticated_user_id),
        assessment_service: ConversationTurnAssessmentService = Depends(get_assessment_service),
    ) -> dict:
        if type(authenticated_user_id) is not UUID:
            raise HTTPException(status_code=401, detail='Authentication required')
        if not isinstance(assessment_service, ConversationTurnAssessmentService):
            raise HTTPException(status_code=503, detail='Assessment unavailable')
        try:
            result = assessment_service.assess(
                authenticated_user_id=authenticated_user_id,
                practice_session_id=practice_session_id,
                conversation_turn_id=turn_id,
                client_request_id=payload.client_request_id,
                scenario_type=scenario_type,
                evaluator_version=evaluator_version,
            )
        except (TurnAssessmentError, EvaluatorFailure):
            # Avoid leaking whether another user's turn exists.
            raise HTTPException(status_code=404, detail='Assessment unavailable') from None
        except Exception:
            raise HTTPException(status_code=503, detail='Assessment unavailable') from None
        # No original text, prompt, raw model response or audio in HTTP output.
        assessment = result.assessment
        if not is_dataclass(assessment):
            raise HTTPException(status_code=503, detail='Assessment unavailable')
        return {
            'turn_id': str(result.turn_id),
            'client_request_id': str(result.client_request_id),
            'text_sha256': result.text_sha256,
            'scenario_type': result.scenario_type,
            'evaluator_version': result.evaluator_version,
            'assessment': asdict(assessment),
        }

    return router
