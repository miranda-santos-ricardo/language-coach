"""Endpoint tests independent of the user's actual auth/database modules."""
from dataclasses import dataclass
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4, UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.conversation_assessment import create_conversation_assessment_router
from app.services.conversation_turn_assessment import (
    ConversationTurnAssessmentService, TurnAssessmentError,
)


@dataclass(frozen=True)
class Assessment:
    schema_version: str = 'test-v1'
    status: str = 'REVIEWED'
    dimensions: tuple = ()


class FakeService(ConversationTurnAssessmentService):
    def __init__(self):
        self.calls = []
        self.failure = None

    def assess(self, **kwargs):
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        return SimpleNamespace(
            turn_id=kwargs['conversation_turn_id'],
            client_request_id=kwargs['client_request_id'],
            text_sha256=sha256(b'Persisted text').hexdigest(),
            evaluator_version=kwargs['evaluator_version'],
            scenario_type=kwargs['scenario_type'],
            assessment=Assessment(),
        )


@pytest.fixture
def setup_client():
    user, practice, turn, request = (uuid4() for _ in range(4))
    service = FakeService()
    def get_auth(): return user
    def get_service(): return service
    app = FastAPI()
    app.include_router(create_conversation_assessment_router(
        get_authenticated_user_id=get_auth,
        get_assessment_service=get_service,
    ))
    url = f'/practice-sessions/{practice}/turns/{turn}/assessment'
    return TestClient(app), service, user, practice, turn, request, url


def test_success_no_untrusted_text(setup_client):
    client, service, user, practice, turn, request, url = setup_client
    res = client.post(url, json={'client_request_id': str(request)})
    assert res.status_code == 200
    assert res.json()['turn_id'] == str(turn)
    assert 'text' not in str(res.json()).lower().replace('text_sha256', '')
    assert service.calls[0]['authenticated_user_id'] == user
    assert service.calls[0]['practice_session_id'] == practice
    assert service.calls[0]['scenario_type'] == 'general'


def test_extra_user_identity_or_text_rejected(setup_client):
    client, service, *_, request, url = setup_client
    for key, value in [('user_id', str(uuid4())), ('text', 'override')]:
        assert client.post(url, json={'client_request_id': str(request), key: value}).status_code == 422
    assert not service.calls


def test_cross_user_and_missing_turn_same_error(setup_client):
    client, service, *_, request, url = setup_client
    for msg in ['Turn unavailable', 'Turn identity, ownership or state mismatch']:
        service.failure = TurnAssessmentError(msg)
        res = client.post(url, json={'client_request_id': str(request)})
        assert res.status_code == 404
        assert res.json() == {'detail': 'Assessment unavailable'}
        assert msg not in res.text


def test_model_failure_no_sensitive_detail(setup_client):
    client, service, *_, request, url = setup_client
    service.failure = RuntimeError('Secret model response')
    res = client.post(url, json={'client_request_id': str(request)})
    assert res.status_code == 503
    assert 'Secret model response' not in res.text


def test_invalid_identity_dependency_rejected():
    app = FastAPI()
    service = FakeService()
    app.include_router(create_conversation_assessment_router(
        get_authenticated_user_id=lambda: 'client-supplied-user',
        get_assessment_service=lambda: service))
    path = f'/practice-sessions/{uuid4()}/turns/{uuid4()}/assessment'
    response = TestClient(app).post(path, json={'client_request_id': str(uuid4())})
    assert response.status_code == 401
    assert service.calls == []


def test_no_auto_registration():
    app = FastAPI()
    path = f'/practice-sessions/{uuid4()}/turns/{uuid4()}/assessment'
    assert TestClient(app).post(path, json={'client_request_id': str(uuid4())}).status_code == 404


def test_path_uuid_and_body_uuid_validation(setup_client):
    client, service, *_, request, url = setup_client
    assert client.post(url, json={'client_request_id': 'nope'}).status_code == 422
    assert client.post('/practice-sessions/nope/turns/nope/assessment', json={'client_request_id': str(request)}).status_code == 422
    assert service.calls == []


def test_factory_requires_dependencies():
    with pytest.raises(ValueError):
        create_conversation_assessment_router(get_authenticated_user_id=None, get_assessment_service=lambda: None)
    with pytest.raises(ValueError):
        create_conversation_assessment_router(get_authenticated_user_id=lambda: uuid4(), get_assessment_service=lambda: None, evaluator_version='')
