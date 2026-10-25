"""Step 8.4.1f — opt-in runtime using persisted external OIDC links.

No interactive login, user auto-provisioning, admin endpoints or legacy app mounting.
Host remains responsible for trusted key rotation, revocation, active-account checks,
secure database configuration and pilot authorization.
"""
from __future__ import annotations

from typing import Callable, Mapping
from uuid import UUID

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.api.learner_pilot_app import create_learner_pilot_app
from app.db.session import get_db
from app.services.assessment_oidc_verifier import OIDCVerifierConfig
from app.services.learner_external_identity import ExternalOIDCLearnerVerifier
from app.services.learner_pilot_routes import oidc_learner_adapter


def create_external_oidc_learner_pilot_app(
    *,
    enabled: bool = False,
    config: OIDCVerifierConfig | None = None,
    public_keys_by_kid: Mapping[str, str] | None = None,
    db_session_factory: Callable[[], Session] | None = None,
    token_is_revoked: Callable[[str], bool] | None = None,
    account_is_active: Callable[[UUID], bool] | None = None,
) -> FastAPI:
    """Instantiate the isolated pilot app only with complete trusted inputs.

    The application's protected routes reuse existing services. Its authentication
    checks JWTs, then resolves a persisted, active (issuer, sub) relationship.
    Invalid configuration raises before any routes are mounted.
    """
    if enabled is not True:
        raise ValueError("External OIDC pilot is disabled by default")
    if config is None or public_keys_by_kid is None:
        raise ValueError("Trusted external OIDC configuration is required")
    verifier = ExternalOIDCLearnerVerifier(
        config=config,
        public_keys_by_kid=public_keys_by_kid,
        db_session_factory=db_session_factory,
        token_is_revoked=token_is_revoked,
        account_is_active=account_is_active,
    )
    pilot_app = create_learner_pilot_app(verify_bearer_token=oidc_learner_adapter(verifier))

    # The OIDC identity-link lookup and all pilot API handlers must use the
    # same database configuration. Otherwise a valid identity can authenticate
    # successfully yet be invisible to the endpoint querying another database.
    # Scope the override to this isolated pilot app, never the default app.
    def pilot_db():
        with db_session_factory() as session:
            yield session

    pilot_app.dependency_overrides[get_db] = pilot_db
    return pilot_app
