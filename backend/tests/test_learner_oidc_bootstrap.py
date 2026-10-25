"""Deterministic tests; no network, external IdP, DB, or paid API calls."""
from datetime import datetime, timezone
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient

from app.services.learner_oidc_bootstrap import (
    LearnerOIDCBootstrapConfig,
    build_learner_oidc_verifier,
    create_oidc_learner_pilot_app,
)


@pytest.fixture
def oidc_material():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    user = uuid4()
    config = LearnerOIDCBootstrapConfig(
        issuer="https://issuer.example.test/", audience="language-coach-pilot",
        public_keys_by_kid={"pinned-key": public_pem},
    )
    def sign(**updates):
        now = int(datetime.now(timezone.utc).timestamp())
        claims = dict(iss=config.issuer, aud=config.audience, sub=str(user),
                      iat=now, nbf=now, exp=now+300, jti=str(uuid4()),
                      scope="learner:access")
        claims.update(updates)
        return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "pinned-key"})
    return config, user, sign


def test_disabled_or_incomplete_bootstrap_fails_closed(oidc_material):
    config, _, _ = oidc_material
    with pytest.raises(ValueError):
        create_oidc_learner_pilot_app()
    with pytest.raises(ValueError):
        create_oidc_learner_pilot_app(enabled=True)
    with pytest.raises(ValueError):
        create_oidc_learner_pilot_app(enabled=True, config=config)


def test_signed_token_produces_verified_learner_identity(oidc_material):
    config, user, sign = oidc_material
    verify = build_learner_oidc_verifier(config=config,
        account_is_active=lambda u: u == user, token_is_revoked=lambda j: False)
    identity = verify(sign())
    assert identity.user_id == user and identity.active
    assert "learner:access" in identity.scopes


@pytest.mark.parametrize("claims", [
    {"iss": "https://evil.example.test/"},
    {"aud": "wrong-audience"},
    {"scope": "conversation:assess"},
    {"sub": "unmapped-external-subject"},
    {"exp": 1},
])
def test_wrong_claims_fail_at_verifier_or_scope_boundary(oidc_material, claims):
    config, user, sign = oidc_material
    app = create_oidc_learner_pilot_app(enabled=True, config=config,
        account_is_active=lambda u: u == user, token_is_revoked=lambda j: False)
    response = TestClient(app).get(f"/users/{user}",
        headers={"Authorization": "Bearer " + sign(**claims)})
    assert response.status_code in (401,403)


def test_revoked_token_fails_closed(oidc_material):
    config, user, sign = oidc_material
    app = create_oidc_learner_pilot_app(enabled=True, config=config,
        account_is_active=lambda u: u == user, token_is_revoked=lambda j: True)
    response = TestClient(app).get(f"/users/{user}",
        headers={"Authorization": "Bearer " + sign()})
    assert response.status_code == 401


def test_inactive_account_fails_closed(oidc_material):
    config, user, sign = oidc_material
    app = create_oidc_learner_pilot_app(enabled=True, config=config,
        account_is_active=lambda u: False, token_is_revoked=lambda j: False)
    response = TestClient(app).get(f"/users/{user}",
        headers={"Authorization": "Bearer " + sign()})
    assert response.status_code == 401


def test_cross_user_fails_before_database(oidc_material):
    config, user, sign = oidc_material
    app = create_oidc_learner_pilot_app(enabled=True, config=config,
        account_is_active=lambda u: u == user, token_is_revoked=lambda j: False)
    response = TestClient(app).get(f"/users/{uuid4()}",
        headers={"Authorization": "Bearer " + sign()})
    assert response.status_code == 404


def test_missing_token_fails_before_database(oidc_material):
    config, user, _ = oidc_material
    app = create_oidc_learner_pilot_app(enabled=True, config=config,
        account_is_active=lambda u: u == user, token_is_revoked=lambda j: False)
    assert TestClient(app).get(f"/users/{user}").status_code == 401


def test_wrong_signature_is_rejected(oidc_material):
    config, user, sign = oidc_material
    other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(datetime.now(timezone.utc).timestamp())
    forged = jwt.encode(dict(iss=config.issuer,aud=config.audience,sub=str(user),
        iat=now,nbf=now,exp=now+60,jti=str(uuid4()),scope="learner:access"),
        other_private,algorithm="RS256",headers={"kid":"pinned-key"})
    app = create_oidc_learner_pilot_app(enabled=True, config=config,
        account_is_active=lambda u: True, token_is_revoked=lambda j: False)
    response = TestClient(app).get(f"/users/{user}",headers={"Authorization":"Bearer "+forged})
    assert response.status_code == 401


def test_non_uuid_subject_is_not_auto_mapped(oidc_material):
    config, user, sign = oidc_material
    verify = build_learner_oidc_verifier(config=config,
        account_is_active=lambda u: True, token_is_revoked=lambda j: False)
    with pytest.raises(Exception):
        verify(sign(sub="provider|opaque-subject"))
