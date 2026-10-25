"""Phase 8.4.1a: opt-in, fail-closed learner identity boundary.

This module does NOT verify JWT signatures or issue tokens. An application host
must supply a genuine verifier before any pilot learner API is secured with it.
It is not mounted by default; route integration is a separate increment.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


LEARNER_SCOPE = "learner:access"
_bearer = HTTPBearer(auto_error=False)


class LearnerAuthenticationSetupError(ValueError):
    """Security configuration is missing or invalid."""


@dataclass(frozen=True)
class VerifiedLearnerIdentity:
    user_id: UUID
    active: bool
    scopes: frozenset[str]


def make_learner_identity_dependency(
    verify_bearer_token: Callable[[str], VerifiedLearnerIdentity],
    *,
    required_scope: str = LEARNER_SCOPE,
):
    """Bind a caller to an identity proven by a host-supplied real verifier.

    No URL, body, cookie, query parameter or custom identity header fallback.
    Token handling stays request-local; never include bearer values in errors.
    """
    if not callable(verify_bearer_token):
        raise LearnerAuthenticationSetupError("A real token verifier is required")
    if type(required_scope) is not str or not required_scope.strip():
        raise LearnerAuthenticationSetupError("Non-empty required scope is required")

    def authenticated_learner(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> UUID:
        if (credentials is None or credentials.scheme.lower() != "bearer"
                or not credentials.credentials):
            raise HTTPException(
                status_code=401, detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            identity = verify_bearer_token(credentials.credentials)
        except Exception:
            raise HTTPException(
                status_code=401, detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
        if (type(identity) is not VerifiedLearnerIdentity
                or type(identity.user_id) is not UUID
                or type(identity.active) is not bool or not identity.active
                or type(identity.scopes) is not frozenset
                or not all(type(scope) is str for scope in identity.scopes)
                or required_scope not in identity.scopes):
            raise HTTPException(status_code=403, detail="Learner access not permitted")
        return identity.user_id

    return authenticated_learner
