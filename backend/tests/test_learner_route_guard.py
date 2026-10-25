"""Isolated 8.4.1b tests; no real endpoints are wired by this increment."""
from uuid import uuid4
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from app.services.learner_identity import (
    LEARNER_SCOPE, VerifiedLearnerIdentity, make_learner_identity_dependency,
)
from app.services.learner_route_guard import require_learner_owner


def make_client():
    owner = uuid4()
    side_effects = []

    def verifier(token):
        if token == "ok":
            return VerifiedLearnerIdentity(owner, True, frozenset({LEARNER_SCOPE}))
        raise ValueError("invalid credential")

    dependency = make_learner_identity_dependency(verifier)
    app = FastAPI()

    @app.post('/users/{user_id}/protected')
    def protected(user_id: __import__('uuid').UUID, identity=Depends(dependency)):
        require_learner_owner(user_id, identity)
        side_effects.append('executed')
        return {'ok': True}

    return TestClient(app), owner, side_effects


def test_owner_request_accepted():
    client, owner, events = make_client()
    response = client.post(f'/users/{owner}/protected', headers={'Authorization': 'Bearer ok'})
    assert response.status_code == 200
    assert events == ['executed']


def test_missing_bearer_denied_before_handler():
    client, owner, events = make_client()
    assert client.post(f'/users/{owner}/protected').status_code == 401
    assert events == []


def test_invalid_bearer_denied_before_handler():
    client, owner, events = make_client()
    assert client.post(f'/users/{owner}/protected', headers={'Authorization': 'Bearer nope'}).status_code == 401
    assert events == []


def test_cross_user_request_hidden_and_has_no_effects():
    client, owner, events = make_client()
    assert client.post(f'/users/{uuid4()}/protected', headers={'Authorization': 'Bearer ok'}).status_code == 404
    assert events == []


def test_spoofed_user_header_never_overrides_token_identity():
    client, owner, events = make_client()
    response = client.post(f'/users/{uuid4()}/protected', headers={
        'Authorization': 'Bearer ok', 'X-User-Id': str(owner),
    })
    assert response.status_code == 404
    assert events == []
