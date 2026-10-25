"""Phase 8.4.1d: explicit, offline, fail-closed OIDC pilot bootstrap.

Keys must be obtained and rotated independently by the trusted deployment host.
This module neither discovers JWKS over the network nor implements login/logout.
The Phase 7 verifier currently supports UUID subjects ONLY.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping
from uuid import UUID

from fastapi import FastAPI

from app.api.learner_pilot_app import create_learner_pilot_app
from app.services.assessment_oidc_verifier import AssessmentOIDCVerifier, OIDCVerifierConfig
from app.services.learner_pilot_routes import oidc_learner_adapter


@dataclass(frozen=True)
class LearnerOIDCBootstrapConfig:
    issuer: str
    audience: str
    public_keys_by_kid: Mapping[str, str]
    algorithm: str = "RS256"
    leeway_seconds: int = 30
    max_token_lifetime_seconds: int = 3600


def build_learner_oidc_verifier(
    *,
    config: LearnerOIDCBootstrapConfig,
    account_is_active: Callable[[UUID], bool],
    token_is_revoked: Callable[[str], bool],
):
    """Create a real signature-checking adapter; reject missing trusted inputs.

    account_is_active MUST be backed by an authoritative current account store.
    token_is_revoked MUST fail closed if revocation status cannot be determined.
    Never substitute callbacks that unconditionally return True/False in production.
    """
    if not isinstance(config, LearnerOIDCBootstrapConfig):
        raise ValueError("Trusted OIDC bootstrap configuration required")
    if not callable(account_is_active) or not callable(token_is_revoked):
        raise ValueError("Authoritative account and revocation checks required")
    verifier = AssessmentOIDCVerifier(
        config=OIDCVerifierConfig(
            issuer=config.issuer,
            audience=config.audience,
            allowed_algorithm=config.algorithm,
            leeway_seconds=config.leeway_seconds,
            max_token_lifetime_seconds=config.max_token_lifetime_seconds,
            # Never grant admin privileges through learner bootstrap.
            admin_scope="conversation:assessment:reconcile",
            required_admin_acr="",
        ),
        public_keys_by_kid=config.public_keys_by_kid,
        account_is_active=account_is_active,
        token_is_revoked=token_is_revoked,
    )
    return oidc_learner_adapter(verifier)


def create_oidc_learner_pilot_app(
    *,
    enabled: bool = False,
    config: LearnerOIDCBootstrapConfig | None = None,
    account_is_active: Callable[[UUID], bool] | None = None,
    token_is_revoked: Callable[[str], bool] | None = None,
) -> FastAPI:
    """Explicitly create an isolated pilot app; no silent fallback to legacy APIs.

    This factory deliberately refuses disabled or incomplete configuration.
    app.main is unchanged and NEVER mounts this app implicitly.
    """
    if enabled is not True:
        raise ValueError("OIDC pilot is disabled by default")
    if config is None:
        raise ValueError("Trusted OIDC configuration required")
    verifier = build_learner_oidc_verifier(
        config=config,
        account_is_active=account_is_active,
        token_is_revoked=token_is_revoked,
    )
    return create_learner_pilot_app(verify_bearer_token=verifier)
