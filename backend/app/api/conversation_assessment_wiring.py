"""Step 5.4b.3: fail-closed, opt-in composition for committed-turn assessment.

This module DOES NOT register endpoints, authenticate callers, or provision LLMs.
Its host must provide a vetted authenticated-user dependency, verified scenario
context mapper, and explicitly permitted evaluator callable. Never derive
identity from URL/body/header without authentication.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, FastAPI
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.conversation_assessment import create_conversation_assessment_router
from app.services.conversation_turn_assessment import ConversationTurnAssessmentService
from app.services.sqlalchemy_turn_resolver import make_sqlalchemy_turn_resolver


class AssessmentWiringError(ValueError):
    pass


def install_assessment_endpoint(
    app: FastAPI,
    *,
    enabled: bool = False,
    authenticated_identity_dependency: Callable[..., Any] | None = None,
    context_from_session: Callable[[object], str] | None = None,
    model_call: Callable[..., Any] | None = None,
    session_dependency: Callable[..., Any] = get_db,
) -> bool:
    """Install only after the host explicitly supplies trusted dependencies.

    Returns False without registering routes when disabled. No implicit identity
    provider, environment-variable auto-enablement, or live provider default.
    """
    if not isinstance(app, FastAPI):
        raise AssessmentWiringError('FastAPI application required')
    if type(enabled) is not bool:
        raise AssessmentWiringError('Explicit boolean enablement required')
    if not enabled:
        return False
    if not all(callable(f) for f in (
        authenticated_identity_dependency, context_from_session,
        model_call, session_dependency,
    )):
        raise AssessmentWiringError('Trusted identity, context, database and evaluator required')
    if getattr(app.state, '_conversation_assessment_installed', False):
        raise AssessmentWiringError('Assessment route already installed')

    def get_authenticated_user_id(user_id: UUID = Depends(authenticated_identity_dependency)) -> UUID:
        if type(user_id) is not UUID:
            raise HTTPException(status_code=401, detail='Authentication required')
        return user_id

    def get_assessment_service(db: Session = Depends(session_dependency)) -> ConversationTurnAssessmentService:
        if not isinstance(db, Session):
            raise HTTPException(status_code=503, detail='Assessment unavailable')
        resolver = make_sqlalchemy_turn_resolver(db, context_from_session=context_from_session)
        # Instance-local cache: NOT persistent or cross-worker idempotency.
        return ConversationTurnAssessmentService(resolve_turn=resolver, model_call=model_call)

    router = create_conversation_assessment_router(
        get_authenticated_user_id=get_authenticated_user_id,
        get_assessment_service=get_assessment_service,
    )
    app.include_router(router)
    app.state._conversation_assessment_installed = True
    return True
