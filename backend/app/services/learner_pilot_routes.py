"""Phase 8.4.1c: fail-closed owner authorization for an opt-in pilot router.

Only a host-provided, cryptographically verified identity may authorize routes.
This does not turn on pilot mode in the default application.
"""
from __future__ import annotations

from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.conversation_turns import router as turns_router
from app.api.language_profiles import router as profiles_router
from app.api.practice_sessions import router as sessions_router
from app.api.users import router as users_router
from app.services.learner_identity import (
    VerifiedLearnerIdentity, make_learner_identity_dependency,
)
from app.services.learner_route_guard import require_learner_owner


def create_guarded_learner_router(
    verify_bearer_token: Callable[[str], VerifiedLearnerIdentity],
) -> APIRouter:
    """Mount existing user routes behind a checked owner boundary.

    Routes without an explicit path user_id (notably /users list/create) are
    deliberately denied. They must not be exposed by this pilot router.
    """
    resolve_user = make_learner_identity_dependency(verify_bearer_token)

    def guard(request: Request, authenticated_user_id: UUID = Depends(resolve_user)) -> None:
        raw_id = request.path_params.get("user_id")
        if raw_id is None:
            raise HTTPException(status_code=404, detail="Not found")
        try:
            path_id = UUID(str(raw_id))
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(status_code=404, detail="Not found") from None
        require_learner_owner(path_id, authenticated_user_id)

    guarded = APIRouter(dependencies=[Depends(guard)])
    for source in (users_router, profiles_router, sessions_router, turns_router):
        guarded.include_router(source)
    return guarded


def oidc_learner_adapter(oidc_verifier: Callable[[str], object]) -> Callable[[str], VerifiedLearnerIdentity]:
    """Adapt the existing AssessmentOIDCVerifier output without weakening it.

    The host must configure trusted keys, issuer, audience, revocation and
    account-status callbacks before supplying the existing OIDC verifier.
    """
    if not callable(oidc_verifier):
        raise ValueError("An OIDC verifier is required")
    from app.api.conversation_assessment_auth import VerifiedIdentity

    def verify(token: str) -> VerifiedLearnerIdentity:
        value = oidc_verifier(token)
        if type(value) is not VerifiedIdentity:
            raise ValueError("Unexpected OIDC identity")
        return VerifiedLearnerIdentity(
            user_id=value.user_id, active=value.active, scopes=value.scopes,
        )
    return verify
