"""Phase 5 Step 7.1 — submit turn only. Read endpoints follow in Step 7.2."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.conversation import ConversationTurnSubmit, ConversationTurnSubmitted
from app.services.conversation_api_dependencies import get_conversation_service
from app.services.conversation_context import (
    ConversationContextNotFoundError, ConversationSessionInactiveError,
)
from app.services.conversation_lock import ConversationBusyError
from app.services.conversation_service import (
    ConversationRequestConflictError, ConversationService, InvalidLearnerUtteranceError,
)
from app.services.llm_errors import (
    LLMConfigurationError, LLMProviderError, LLMRateLimitError, LLMTimeoutError,
)
from app.services.structured_feedback import FeedbackValidationError

router = APIRouter(
    prefix="/users/{user_id}/language-profiles/{profile_id}/sessions/{practice_session_id}/turns",
    tags=["conversation-turns"],
)


@router.post("", response_model=ConversationTurnSubmitted, status_code=status.HTTP_201_CREATED)
def submit_conversation_turn(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    practice_session_id: uuid.UUID,
    payload: ConversationTurnSubmit,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationTurnSubmitted:
    try:
        outcome = service.submit(
            session=db, user_id=user_id, profile_id=profile_id,
            practice_session_id=practice_session_id, text=payload.text,
            input_modality=payload.input_modality,
            client_request_id=payload.client_request_id,
        )
        return ConversationTurnSubmitted(
            turn_id=outcome.turn_id, turn_index=outcome.turn_index,
            coach_response=outcome.coach_response, feedback=outcome.feedback.feedback,
            replayed=outcome.replayed, prompt_version=outcome.prompt_version,
            model=outcome.model,
        )
    except InvalidLearnerUtteranceError as exc:
        raise HTTPException(status_code=400, detail="Invalid learner utterance.") from exc
    except ConversationContextNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation context not found.") from exc
    except ConversationSessionInactiveError as exc:
        raise HTTPException(status_code=409, detail="Practice session is not active.") from exc
    except ConversationRequestConflictError as exc:
        raise HTTPException(status_code=409, detail="Request ID conflicts with an existing turn.") from exc
    except ConversationBusyError as exc:
        raise HTTPException(status_code=409, detail="Practice session is processing another turn.", headers={"Retry-After": "1"}) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Conversation provider is not configured.") from exc
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail="Conversation provider timed out.") from exc
    except (LLMRateLimitError, LLMProviderError) as exc:
        raise HTTPException(status_code=503, detail="Conversation provider is temporarily unavailable.") from exc
    except FeedbackValidationError as exc:
        raise HTTPException(status_code=502, detail="Conversation provider returned invalid structured feedback.") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Conversation persistence is temporarily unavailable.") from exc


from fastapi import Query
from app.schemas.conversation import ConversationTurnDetail, ConversationTurnPage, persisted_turn_response
from app.services.conversation_api_dependencies import get_conversation_read_service
from app.services.conversation_read_service import ConversationReadService


@router.get("", response_model=ConversationTurnPage)
def list_conversation_turns(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    practice_session_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    service: ConversationReadService = Depends(get_conversation_read_service),
) -> ConversationTurnPage:
    try:
        turns = service.list_turns(
            session=db, user_id=user_id, profile_id=profile_id,
            practice_session_id=practice_session_id, limit=limit, offset=offset,
        )
        return ConversationTurnPage(
            items=[persisted_turn_response(turn) for turn in turns],
            limit=limit, offset=offset,
        )
    except ConversationContextNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation context not found.") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Conversation persistence is temporarily unavailable.") from exc


@router.get("/{turn_id}", response_model=ConversationTurnDetail)
def get_conversation_turn(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    practice_session_id: uuid.UUID,
    turn_id: uuid.UUID,
    db: Session = Depends(get_db),
    service: ConversationReadService = Depends(get_conversation_read_service),
) -> ConversationTurnDetail:
    try:
        turn = service.get_turn(
            session=db, user_id=user_id, profile_id=profile_id,
            practice_session_id=practice_session_id, turn_id=turn_id,
        )
        return persisted_turn_response(turn)
    except ConversationContextNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation context not found.") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Conversation persistence is temporarily unavailable.") from exc
