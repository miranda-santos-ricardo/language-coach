"""Step 7.1 API contract and controlled error mapping; no OpenAI calls."""
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.conversation_api_dependencies import get_conversation_service
from app.services.conversation_context import ConversationContextNotFoundError, ConversationSessionInactiveError
from app.services.conversation_lock import ConversationBusyError
from app.services.conversation_service import ConversationRequestConflictError, InvalidLearnerUtteranceError
from app.services.llm_errors import LLMConfigurationError, LLMProviderError, LLMRateLimitError, LLMTimeoutError
from app.services.structured_feedback import CoachTurnOutput, FeedbackValidationError
from tests.test_conversation_context_integration import create_case
from tests.test_conversation_service import FakeLLM
from app.services.conversation_service import ConversationService


def url(u, p, s):
    return f"/users/{u.id}/language-profiles/{p.id}/sessions/{s.id}/turns"


def request_body(**changes):
    return {"text": "Bonjour", "input_modality": "text", "client_request_id": str(uuid.uuid4()), **changes}


def test_post_success_persists_feedback_and_replay(api_client, service_session):
    u, p, s = create_case(service_session)
    provider = FakeLLM()
    app.dependency_overrides[get_conversation_service] = lambda: ConversationService(llm=provider)
    try:
        body = request_body()
        first = api_client.post(url(u,p,s), json=body)
        assert first.status_code == 201, first.text
        data = first.json()
        assert data["turn_index"] == 1 and data["feedback"]["grammar"]["status"] == "correct"
        assert data["prompt_version"] == "coach-v3" and data["replayed"] is False
        second = api_client.post(url(u,p,s), json=body)
        assert second.status_code == 201 and second.json()["turn_id"] == data["turn_id"]
        assert second.json()["replayed"] is True and len(provider.calls) == 1
        conflict = api_client.post(url(u,p,s), json={**body, "text": "Different"})
        assert conflict.status_code == 409 and len(provider.calls) == 1
    finally:
        app.dependency_overrides.pop(get_conversation_service, None)


@pytest.mark.parametrize("changes", [
    {"text": ""}, {"text": "x" * 4001}, {"input_modality": "wrong"},
    {"client_request_id": "not-uuid"}, {"unexpected": 1},
])
def test_invalid_http_payload_is_422(api_client, service_session, changes):
    u,p,s=create_case(service_session)
    response=api_client.post(url(u,p,s), json=request_body(**changes))
    assert response.status_code == 422


@pytest.mark.parametrize("error,code,detail", [
    (ConversationContextNotFoundError("private"),404,"Conversation context not found."),
    (ConversationSessionInactiveError("private"),409,"Practice session is not active."),
    (ConversationRequestConflictError("private"),409,"Request ID conflicts with an existing turn."),
    (ConversationBusyError("private"),409,"Practice session is processing another turn."),
    (InvalidLearnerUtteranceError("private"),400,"Invalid learner utterance."),
    (LLMConfigurationError("private"),503,"Conversation provider is not configured."),
    (LLMRateLimitError("private"),503,"Conversation provider is temporarily unavailable."),
    (LLMProviderError("private"),503,"Conversation provider is temporarily unavailable."),
    (LLMTimeoutError("private"),504,"Conversation provider timed out."),
    (FeedbackValidationError("private"),502,"Conversation provider returned invalid structured feedback."),
])
def test_known_errors_are_sanitized(api_client, service_session, error, code, detail):
    u,p,s=create_case(service_session)
    class BrokenService:
        def submit(self, **kwargs):
            raise error
    app.dependency_overrides[get_conversation_service] = lambda: BrokenService()
    try:
        response=api_client.post(url(u,p,s), json=request_body())
        assert response.status_code == code
        assert response.json() == {"detail":detail}
        assert "private" not in response.text
        if isinstance(error, ConversationBusyError):
            assert response.headers["retry-after"] == "1"
    finally:
        app.dependency_overrides.pop(get_conversation_service,None)


def test_cross_profile_is_404_without_llm(api_client, service_session):
    u,p,s=create_case(service_session)
    other,_,_=create_case(service_session)
    llm=FakeLLM()
    app.dependency_overrides[get_conversation_service]=lambda: ConversationService(llm=llm)
    try:
        response=api_client.post(f"/users/{other.id}/language-profiles/{p.id}/sessions/{s.id}/turns",json=request_body())
        assert response.status_code==404 and not llm.calls
    finally:
        app.dependency_overrides.pop(get_conversation_service,None)
