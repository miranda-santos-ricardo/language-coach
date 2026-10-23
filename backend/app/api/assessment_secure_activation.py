"""Step 5.4b.12: explicit, fail-closed mounting of both assessment routes.

This integrates an already configured OIDC verifier; it does not provision an
identity provider, retrieve JWKS, or approve production release by itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.api.assessment_admin_recovery import install_assessment_admin_recovery
from app.api.conversation_assessment_persistent import install_persistent_assessment_endpoint
from app.services.assessment_activation_readiness import (
    ReadinessReport, REQUIRED_ATTESTATIONS,
)
from app.services.assessment_oidc_verifier import AssessmentOIDCVerifier


class SecureActivationDenied(ValueError):
    pass


@dataclass(frozen=True)
class SecureActivationDependencies:
    verifier: AssessmentOIDCVerifier
    context_from_session: Callable
    model_call: Callable
    session_dependency: Callable
    ledger_session_factory: Callable[[], Session]


def install_secured_assessment_routes(
    app: FastAPI,
    *,
    enabled: bool = False,
    readiness: ReadinessReport | None = None,
    dependencies: SecureActivationDependencies | None = None,
) -> bool:
    """Mount both routes only after an explicit GO and concrete OIDC verifier.

    This is a deployment assembly guard, not a security certification. A GO
    report includes operational attestations whose truth must be independently
    verified by the deployer. Configure all dependencies before calling.
    """
    if not isinstance(app, FastAPI) or type(enabled) is not bool:
        raise SecureActivationDenied("FastAPI and explicit boolean flag required")
    if not enabled:
        return False
    if not isinstance(readiness, ReadinessReport) or readiness.verdict != "GO" or not readiness.findings or readiness.blockers:
        raise SecureActivationDenied("Readiness GO with no blockers required")
    checks = {f.check: f for f in readiness.findings}
    required_checks = {
        "trusted_token_verifier_supplied", "model_evaluator_supplied",
        "request_db_dependency_supplied", "independent_ledger_factory_supplied",
        "trusted_context_resolver_supplied", "postgresql_connection",
        "alembic_head", "assessment_tables", *REQUIRED_ATTESTATIONS,
    }
    if len(checks) != len(readiness.findings) or any(
        key not in checks or checks[key].passed is not True
        or checks[key].evidence_kind != ("attested" if key in REQUIRED_ATTESTATIONS else "measured")
        for key in required_checks
    ):
        raise SecureActivationDenied("Complete and attributable readiness evidence required")
    if not isinstance(dependencies, SecureActivationDependencies):
        raise SecureActivationDenied("Typed dependencies required")
    if not isinstance(dependencies.verifier, AssessmentOIDCVerifier):
        raise SecureActivationDenied("Concrete OIDC token verifier required")
    if not all(callable(x) for x in (
        dependencies.context_from_session, dependencies.model_call,
        dependencies.session_dependency, dependencies.ledger_session_factory,
    )):
        raise SecureActivationDenied("Incomplete dependencies")
    if (getattr(app.state, "_conversation_assessment_installed", False)
            or getattr(app.state, "_assessment_admin_recovery_installed", False)
            or getattr(app.state, "_secured_assessment_routes_installed", False)):
        raise SecureActivationDenied("Assessment or recovery route already mounted")
    # Mount only after all preflight checks. No network calls or DB writes here.
    install_persistent_assessment_endpoint(
        app, enabled=True, verify_bearer_token=dependencies.verifier,
        context_from_session=dependencies.context_from_session,
        model_call=dependencies.model_call,
        session_dependency=dependencies.session_dependency,
        ledger_session_factory=dependencies.ledger_session_factory,
    )
    install_assessment_admin_recovery(
        app, enabled=True, verify_bearer_token=dependencies.verifier,
        session_dependency=dependencies.session_dependency,
    )
    app.state._secured_assessment_routes_installed = True
    return True
