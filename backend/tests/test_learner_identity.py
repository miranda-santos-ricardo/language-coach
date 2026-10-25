"""Deterministic security-contract tests; fake verifier is NOT pilot-ready OIDC."""
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.services.learner_identity import (
    LEARNER_SCOPE, LearnerAuthenticationSetupError,
    VerifiedLearnerIdentity, make_learner_identity_dependency,
)


def _client():
    owner = uuid4()
    calls = []

    def verify(token: str):
        calls.append(token)
        if token == "valid":
            return VerifiedLearnerIdentity(owner, True, frozenset({LEARNER_SCOPE}))
        if token == "wrong-scope":
            return VerifiedLearnerIdentity(owner, True, frozenset({"conversation:assess"}))
        if token == "inactive":
            return VerifiedLearnerIdentity(owner, False, frozenset({LEARNER_SCOPE}))
        if token == "malformed-result":
            return {"user_id": str(owner)}
        raise ValueError("secret provider diagnostics")

    app = FastAPI()
    dependency = make_learner_identity_dependency(verify)

    @app.get("/users/{user_id}/secure-test")
    def secure_test(user_id: str, actual_user=Depends(dependency)):
        if user_id != str(actual_user):
            # Example owner enforcement; subsequent increment must apply at every route.
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        return {"user_id": str(actual_user)}

    return TestClient(app), owner, calls


def test_authentication_is_required():
    client, owner, calls = _client()
    result = client.get(f"/users/{owner}/secure-test")
    assert result.status_code == 401
    assert result.headers["www-authenticate"] == "Bearer"
    assert calls == []


def test_token_verifier_identity_is_authoritative():
    client, owner, calls = _client()
    r = client.get(f"/users/{owner}/secure-test", headers={"Authorization": "Bearer valid", "X-User-Id": str(uuid4())})
    assert r.status_code == 200
    assert r.json() == {"user_id": str(owner)}
    assert calls == ["valid"]


def test_foreign_user_path_is_rejected():
    client, owner, calls = _client()
    r = client.get(f"/users/{uuid4()}/secure-test", headers={"Authorization": "Bearer valid"})
    assert r.status_code == 404
    assert calls == ["valid"]


@pytest.mark.parametrize("token,expected", [
    ("expired", 401), ("wrong-scope", 403), ("inactive", 403),
    ("malformed-result", 403),
])
def test_bad_token_or_principal_is_denied_without_leak(token, expected):
    client, owner, _ = _client()
    r = client.get(f"/users/{owner}/secure-test", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == expected
    assert "secret provider diagnostics" not in r.text


def test_missing_verifier_fails_at_configuration_time():
    with pytest.raises(LearnerAuthenticationSetupError):
        make_learner_identity_dependency(None)


def test_missing_scope_fails_at_configuration_time():
    with pytest.raises(LearnerAuthenticationSetupError):
        make_learner_identity_dependency(lambda token: None, required_scope="")
