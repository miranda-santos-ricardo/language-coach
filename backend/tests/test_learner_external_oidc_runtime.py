"""Phase 8.4.1f isolated app integration tests (no paid API calls)."""
from datetime import datetime, timezone
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.db.base import Base
from app.models.oidc_identity_link import OIDCIdentityLink  # noqa: F401
from app.models.user import User
from app.services.assessment_oidc_verifier import OIDCVerifierConfig
from app.services.learner_external_identity import provision_link, revoke_link
from app.services.learner_external_oidc_runtime import create_external_oidc_learner_pilot_app

ISSUER = "https://auth.example.test/"
SUBJECT = "external|learner"


@pytest.fixture
def context():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    owner, other = uuid4(), uuid4()
    with Session(engine) as db:
        db.add_all([User(id=owner, display_name="Owner"), User(id=other, display_name="Other")])
        db.commit()
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    config = OIDCVerifierConfig(issuer=ISSUER, audience="language-coach-pilot")
    revoked = set()
    active = {owner, other}
    def app(db_factory=None):
        return create_external_oidc_learner_pilot_app(
            enabled=True, config=config, public_keys_by_kid={"key-1": public},
            db_session_factory=db_factory or (lambda: Session(engine)),
            token_is_revoked=lambda jti: jti in revoked,
            account_is_active=lambda user_id: user_id in active,
        )
    def sign(**updates):
        now = int(datetime.now(timezone.utc).timestamp())
        claims = dict(iss=ISSUER, sub=SUBJECT, aud="language-coach-pilot", iat=now,
                      nbf=now-1, exp=now+300, jti="unique-jti", scope="learner:access")
        claims.update(updates)
        return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "key-1"})
    yield engine, owner, other, app, sign, revoked, active
    engine.dispose()


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _link(engine, owner):
    with Session(engine) as db:
        provision_link(db, issuer=ISSUER, subject=SUBJECT, user_id=owner)
        db.commit()


def test_requires_explicit_enablement_and_configuration(context):
    _, _, _, app, _, _, _ = context
    with pytest.raises(ValueError, match="disabled"):
        create_external_oidc_learner_pilot_app()
    with pytest.raises(ValueError, match="configuration"):
        create_external_oidc_learner_pilot_app(enabled=True)
    assert app() is not None


def test_unlinked_or_unauthenticated_cannot_reach_service(context):
    _, owner, _, app, sign, _, _ = context
    client = TestClient(app())
    assert client.get(f"/users/{owner}").status_code == 401
    assert client.get(f"/users/{owner}", headers=_headers(sign())).status_code == 401


def test_linked_identity_resolves_existing_user_and_forbids_other(context):
    engine, owner, other, app, sign, _, _ = context
    _link(engine, owner)
    client = TestClient(app())
    response = client.get(f"/users/{owner}", headers=_headers(sign()))
    assert response.status_code == 200
    assert response.json()["id"] == str(owner)
    assert client.get(f"/users/{other}", headers=_headers(sign())).status_code == 404
    assert client.get("/users", headers=_headers(sign())).status_code == 404
    assert client.post("/users", headers=_headers(sign()), json={}).status_code == 404


def test_revoked_link_is_denied_immediately(context):
    engine, owner, _, app, sign, _, _ = context
    _link(engine, owner)
    client = TestClient(app())
    assert client.get(f"/users/{owner}", headers=_headers(sign())).status_code == 200
    with Session(engine) as db:
        assert revoke_link(db, issuer=ISSUER, subject=SUBJECT)
        db.commit()
    assert client.get(f"/users/{owner}", headers=_headers(sign())).status_code == 401


@pytest.mark.parametrize("claims", [
    {"iss": "https://wrong.test/"}, {"aud": "wrong-audience"},
    {"scope": "unrelated"}, {"sub": "unknown"}, {"exp": 1},
])
def test_invalid_token_claims_are_denied(context, claims):
    engine, owner, _, app, sign, _, _ = context
    _link(engine, owner)
    assert TestClient(app()).get(f"/users/{owner}", headers=_headers(sign(**claims))).status_code == 401


def test_inactive_account_and_revoked_jti_are_denied(context):
    engine, owner, _, app, sign, revoked, active = context
    _link(engine, owner)
    client = TestClient(app())
    active.remove(owner)
    assert client.get(f"/users/{owner}", headers=_headers(sign())).status_code == 401
    active.add(owner)
    revoked.add("unique-jti")
    assert client.get(f"/users/{owner}", headers=_headers(sign())).status_code == 401


def test_database_failure_fails_closed(context):
    engine, owner, _, app, sign, _, _ = context
    _link(engine, owner)
    def unavailable():
        raise RuntimeError("database unavailable")
    client = TestClient(app(db_factory=unavailable))
    response = client.get(f"/users/{owner}", headers=_headers(sign()))
    assert response.status_code == 401
    assert "database unavailable" not in response.text


def test_default_application_is_not_modified():
    from app.main import app
    from app.services.learner_external_oidc_runtime import create_external_oidc_learner_pilot_app
    assert not any(getattr(r, "path", "").startswith("/pilot/") for r in app.routes)
    assert callable(create_external_oidc_learner_pilot_app)


def test_pilot_routes_use_same_database_factory_as_oidc(context):
    engine, owner, _, app, sign, _, _ = context
    _link(engine, owner)
    pilot = app()
    assert get_db in pilot.dependency_overrides
    client = TestClient(pilot)
    response = client.get(f"/users/{owner}", headers=_headers(sign()))
    assert response.status_code == 200
    assert response.json()["id"] == str(owner)


def test_pilot_me_uses_server_derived_identity(context):
    engine, owner, other, app, sign, _, _ = context
    _link(engine, owner)
    client = TestClient(app())
    assert client.get('/pilot/me').status_code == 401
    response = client.get('/pilot/me', headers=_headers(sign()))
    assert response.status_code == 200
    assert response.json()['id'] == str(owner)
    assert response.json()['id'] != str(other)
    with Session(engine) as db:
        assert revoke_link(db, issuer=ISSUER, subject=SUBJECT)
        db.commit()
    assert client.get('/pilot/me', headers=_headers(sign())).status_code == 401
