"""Signed-token HTTP integration; SQLite harness only, not production PostgreSQL."""
from datetime import datetime, timezone
from uuid import uuid4
import sys
from types import ModuleType

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.persistent_assessment_idempotency import AssessmentLedgerBase
from app.services.assessment_reconciliation import AssessmentReconciliationEvent
from tests.support.assessment_models import (
    Base, LanguageVariant, LanguageProfile, PracticeSession, ConversationTurn
)

from app.api.assessment_secure_activation import (
    SecureActivationDependencies, SecureActivationDenied,
    install_secured_assessment_routes,
)
from app.services.assessment_activation_readiness import ReadinessFinding, ReadinessReport, REQUIRED_ATTESTATIONS
from app.services.assessment_oidc_verifier import AssessmentOIDCVerifier, OIDCVerifierConfig


@pytest.fixture
def auth():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    user = uuid4()
    config = OIDCVerifierConfig(
        issuer="https://identity.example.test/", audience="language-coach-api", required_admin_acr="mfa"
    )
    verifier = AssessmentOIDCVerifier(
        config=config, public_keys_by_kid={"key-1": public},
        account_is_active=lambda uid: uid == user, token_is_revoked=lambda jti: False,
    )

    def sign(*, scope="conversation:assess", subject=None, acr=None, aud=None):
        now = int(datetime.now(timezone.utc).timestamp())
        claims = dict(iss=config.issuer, aud=aud or config.audience, sub=str(subject or user),
                      iat=now-1, nbf=now-1, exp=now+300, jti=str(uuid4()), scope=scope)
        if acr is not None:
            claims["acr"] = acr
        return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "key-1"})
    return verifier, sign


@pytest.fixture
def harness(tmp_path, auth, monkeypatch):
    model_module = ModuleType("app.models")
    for model in (LanguageVariant, LanguageProfile, PracticeSession, ConversationTurn):
        setattr(model_module, model.__name__, model)
    monkeypatch.setitem(sys.modules, "app.models", model_module)
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'secure.db'}")
    Base.metadata.create_all(engine)
    AssessmentLedgerBase.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    def session_dependency():
        with factory() as db:
            yield db
    deps = SecureActivationDependencies(
        verifier=auth[0], context_from_session=lambda session: "professional",
        model_call=lambda request: {}, session_dependency=session_dependency,
        ledger_session_factory=factory,
    )
    technical = (
        "trusted_token_verifier_supplied", "model_evaluator_supplied",
        "request_db_dependency_supplied", "independent_ledger_factory_supplied",
        "trusted_context_resolver_supplied", "postgresql_connection",
        "alembic_head", "assessment_tables",
    )
    # Synthetic GO is deliberately confined to the unit test fixture. It is NOT
    # an actual PostgreSQL/operational attestation for deployment.
    report = ReadinessReport("GO", tuple(
        ReadinessFinding(k, True, "synthetic-test-only", "measured") for k in technical
    ) + tuple(ReadinessFinding(k, True, "synthetic-test-only", "attested") for k in REQUIRED_ATTESTATIONS))
    yield FastAPI(), deps, report, auth[1]
    engine.dispose()


def test_disabled_never_mounts(harness):
    app, deps, report, _ = harness
    assert install_secured_assessment_routes(app, dependencies=deps, readiness=report) is False
    assert TestClient(app).post(f"/admin/assessments/{uuid4()}/reconcile-as-failed").status_code == 404

@pytest.mark.parametrize("report", [None, ReadinessReport("NO_GO", ()), ReadinessReport("GO", ()),
                                  ReadinessReport("GO", (ReadinessFinding("missing", False, "", "missing"),))])
def test_fail_closed_readiness(harness, report):
    app, deps, _, _ = harness
    with pytest.raises(SecureActivationDenied):
        install_secured_assessment_routes(app, enabled=True, dependencies=deps, readiness=report)
    assert not getattr(app.state, "_conversation_assessment_installed", False)


def test_verifier_cannot_be_generic_callable(harness):
    app, deps, report, _ = harness
    invalid = SecureActivationDependencies(lambda token: None, deps.context_from_session, deps.model_call,
                                           deps.session_dependency, deps.ledger_session_factory)
    with pytest.raises(SecureActivationDenied):
        install_secured_assessment_routes(app, enabled=True, dependencies=invalid, readiness=report)


def test_signed_jwt_http_admin_auth_and_scope(harness):
    app, deps, report, sign = harness
    assert install_secured_assessment_routes(app, enabled=True, dependencies=deps, readiness=report)
    client = TestClient(app)
    path = f"/admin/assessments/{uuid4()}/reconcile-as-failed"
    body = {"reason_code": "WORKER_TERMINATED", "ticket_reference": "INC-77"}
    def post(token):
        headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
        return client.post(path, json=body, headers=headers)
    assert post(None).status_code == 401
    assert post("not-a-token").status_code == 401
    assert post(sign()).status_code == 403  # ordinary learner scope
    assert post(sign(scope="conversation:assessment:reconcile")).status_code == 401  # MFA assertion missing
    assert post(sign(scope="conversation:assessment:reconcile", acr="mfa", aud="other")).status_code == 401
    assert post(sign(scope="conversation:assessment:reconcile", acr="mfa")).status_code == 409  # authenticated; missing record


def test_signed_jwt_http_assessment_auth(harness):
    app, deps, report, sign = harness
    install_secured_assessment_routes(app, enabled=True, dependencies=deps, readiness=report)
    client = TestClient(app)
    path = f"/practice-sessions/{uuid4()}/turns/{uuid4()}/assessment"
    body = {"client_request_id": str(uuid4())}
    def post(token):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return client.post(path, json=body, headers=headers)
    assert post(None).status_code == 401
    assert post("bogus").status_code == 401
    assert post(sign(scope="conversation:assessment:reconcile", acr="mfa")).status_code == 403
    assert post(sign()).status_code in (404, 503)  # authorized boundary reached, missing schema/turn


def test_duplicate_activation_is_rejected(harness):
    app, deps, report, _ = harness
    install_secured_assessment_routes(app, enabled=True, dependencies=deps, readiness=report)
    with pytest.raises(SecureActivationDenied):
        install_secured_assessment_routes(app, enabled=True, dependencies=deps, readiness=report)


def test_incomplete_go_never_mounts(harness):
    app, deps, _, _ = harness
    fabricated = ReadinessReport("GO", (ReadinessFinding("deployment_review", True, "claimed", "attested"),))
    with pytest.raises(SecureActivationDenied):
        install_secured_assessment_routes(app, enabled=True, dependencies=deps, readiness=fabricated)


def test_duplicate_finding_never_mounts(harness):
    app, deps, report, _ = harness
    duplicate = ReadinessReport("GO", report.findings + (report.findings[0],))
    with pytest.raises(SecureActivationDenied):
        install_secured_assessment_routes(app, enabled=True, dependencies=deps, readiness=duplicate)
