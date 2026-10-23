"""Step 5.4b.4: fail-closed authentication boundary for optional assessments.

This is NOT a token issuer or verifier. The host MUST inject a real verifier
validating signature, issuer, audience, expiration, revocation if applicable,
and account status. Never parse an unverified JWT or trust X-User-Id.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from uuid import UUID
from fastapi import FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import Depends
from app.api.conversation_assessment_wiring import install_assessment_endpoint

class AuthenticationSetupError(ValueError):
    pass

class AuthenticationDenied(Exception):
    """Verifier rejection; do not expose its details to clients."""

@dataclass(frozen=True)
class VerifiedIdentity:
    user_id: UUID
    active: bool
    scopes: frozenset[str]

_REQUIRED_SCOPE = 'conversation:assess'
_bearer = HTTPBearer(auto_error=False)


def make_authenticated_identity_dependency(
    verify_bearer_token: Callable[[str], VerifiedIdentity],
):
    """Only trust a host-supplied, cryptographically verified identity."""
    if not callable(verify_bearer_token):
        raise AuthenticationSetupError('Verified-token dependency required')

    def authenticated_identity(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> UUID:
        # Never fall back to URL/body/query/cookies/custom identity headers.
        if credentials is None or credentials.scheme.lower() != 'bearer' or not credentials.credentials:
            raise HTTPException(status_code=401, detail='Authentication required', headers={'WWW-Authenticate':'Bearer'})
        try:
            identity = verify_bearer_token(credentials.credentials)
        except Exception:
            # Do not leak verifier implementation, token, user existence or expiry.
            raise HTTPException(status_code=401, detail='Authentication required', headers={'WWW-Authenticate':'Bearer'}) from None
        if (type(identity) is not VerifiedIdentity or type(identity.user_id) is not UUID
                or type(identity.active) is not bool or not identity.active
                or type(identity.scopes) is not frozenset
                or not all(type(s) is str for s in identity.scopes)
                or _REQUIRED_SCOPE not in identity.scopes):
            raise HTTPException(status_code=403, detail='Assessment not permitted')
        return identity.user_id

    return authenticated_identity


def install_authenticated_assessment_endpoint(
    app: FastAPI, *, enabled: bool = False,
    verify_bearer_token: Callable[[str], VerifiedIdentity] | None = None,
    context_from_session=None, model_call=None, session_dependency=None,
) -> bool:
    """Explicit opt-in; no route mounts until every dependency is provided."""
    if type(enabled) is not bool:
        raise AuthenticationSetupError('Boolean enablement required')
    if not enabled:
        return False
    if not callable(verify_bearer_token):
        raise AuthenticationSetupError('Real verified-token dependency required')
    if not all(callable(f) for f in (context_from_session, model_call, session_dependency)):
        raise AuthenticationSetupError('Context, evaluator and request-scoped DB required')
    return install_assessment_endpoint(
        app, enabled=True,
        authenticated_identity_dependency=make_authenticated_identity_dependency(verify_bearer_token),
        context_from_session=context_from_session,
        model_call=model_call,
        session_dependency=session_dependency,
    )
