from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.learner_pilot_app import create_learner_pilot_app
from app.services.learner_identity import VerifiedLearnerIdentity
from app.services.learner_pilot_routes import oidc_learner_adapter
from app.api.conversation_assessment_auth import VerifiedIdentity

OWNER = uuid4()
OTHER = uuid4()


def verifier(token: str):
    if token != "signed-and-verified-placeholder":
        raise ValueError("invalid")
    return VerifiedLearnerIdentity(OWNER, True, frozenset({"learner:access"}))


@pytest.fixture
def client():
    return TestClient(create_learner_pilot_app(verify_bearer_token=verifier))


@pytest.mark.parametrize("path", [
    f"/users/{OWNER}",
    f"/users/{OWNER}/language-profiles",
    f"/users/{OWNER}/language-profiles/{uuid4()}/sessions",
    f"/users/{OWNER}/language-profiles/{uuid4()}/sessions/{uuid4()}/turns",
])
def test_owner_routes_require_bearer_before_db_or_llm(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer invalid"}).status_code == 401


@pytest.mark.parametrize("path", [
    f"/users/{OTHER}",
    f"/users/{OTHER}/language-profiles",
    f"/users/{OTHER}/language-profiles/{uuid4()}/sessions",
    f"/users/{OTHER}/language-profiles/{uuid4()}/sessions/{uuid4()}/turns",
])
def test_other_user_routes_denied_before_service(client, path):
    result = client.get(path, headers={"Authorization": "Bearer signed-and-verified-placeholder"})
    assert result.status_code == 404


def test_no_unscoped_users_listing_or_create(client):
    headers = {"Authorization": "Bearer signed-and-verified-placeholder"}
    assert client.get("/users", headers=headers).status_code == 404
    assert client.post("/users", headers=headers, json={}).status_code == 404


def test_missing_verifier_fails_before_mount():
    with pytest.raises(ValueError):
        create_learner_pilot_app(verify_bearer_token=None)


def test_existing_oidc_identity_can_be_adapted_without_trusting_path():
    real = VerifiedIdentity(OWNER, True, frozenset({"learner:access"}))
    adapted = oidc_learner_adapter(lambda _token: real)("token")
    assert adapted.user_id == OWNER
    assert adapted.scopes == frozenset({"learner:access"})


def test_wrong_oidc_result_rejected():
    with pytest.raises(ValueError):
        oidc_learner_adapter(lambda _token: {"user_id": str(OWNER)})("bad")


def test_default_main_does_not_mount_pilot_routes():
    from app.main import app
    assert not any(getattr(r, "path", "").startswith("/pilot/") for r in app.routes)
