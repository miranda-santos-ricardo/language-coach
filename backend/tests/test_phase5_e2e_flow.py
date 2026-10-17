"""Phase 5 Step 11: HTTP-level integration, real temporary ORM, fake external providers.

No OpenAI calls, no external Postgres, and no real audio or microphone.
"""
import uuid

import pytest
from sqlalchemy import func, select

from app.api import practice_sessions
from app.main import app
from app.models import ConversationTurn, LanguageFeedback
from app.schemas.transcription import TranscriptionResult
from app.services.conversation_api_dependencies import get_conversation_service
from app.services.conversation_service import ConversationService
from app.services.llm_errors import LLMTimeoutError
from tests.test_conversation_context_integration import create_case
from tests.test_conversation_service import FakeLLM


class FakeSTT:
    def __init__(self, transcript="Bonjour, je voudrais pratiquer mon français."):
        self.transcript = transcript
        self.calls = []

    def transcribe(self, **kwargs):
        self.calls.append(kwargs)
        return TranscriptionResult(transcript=self.transcript, language="fr")


def base_url(user, profile, practice):
    return f"/users/{user.id}/language-profiles/{profile.id}/sessions/{practice.id}"


def post_turn(client, base, text, *, modality="text", request_id=None):
    return client.post(base + "/turns", json={
        "text": text, "input_modality": modality,
        "client_request_id": str(request_id or uuid.uuid4()),
    })


@pytest.fixture
def mocked_providers(api_client, monkeypatch):
    stt = FakeSTT()
    llm = FakeLLM()
    monkeypatch.setattr(practice_sessions, "get_transcription_service", lambda: stt)
    app.dependency_overrides[get_conversation_service] = lambda: ConversationService(llm=llm)
    try:
        yield api_client, stt, llm
    finally:
        app.dependency_overrides.pop(get_conversation_service, None)


def test_voice_transcription_requires_explicit_post_then_persists_feedback(mocked_providers, service_session):
    client, stt, llm = mocked_providers
    u, p, s = create_case(service_session)
    base = base_url(u, p, s)
    transcribed = client.post(base + "/transcriptions", files={
        "audio": ("sample.webm", b"synthetic-audio-bytes", "audio/webm")
    })
    assert transcribed.status_code == 200, transcribed.text
    transcript = transcribed.json()["transcript"]
    assert transcript == stt.transcript
    assert len(stt.calls) == 1
    assert llm.calls == []  # STT never submits to AI without explicit request
    assert client.get(base + "/turns").json()["items"] == []

    edited = transcript.replace("pratiquer", "améliorer")
    submitted = post_turn(client, base, edited, modality="voice")
    assert submitted.status_code == 201, submitted.text
    payload = submitted.json()
    assert payload["turn_index"] == 1
    assert payload["feedback"]["grammar"]["status"] == "correct"
    assert len(llm.calls) == 1

    history = client.get(base + "/turns").json()["items"]
    assert len(history) == 1
    assert history[0]["learner_text"] == edited
    assert history[0]["input_modality"] == "voice"
    assert client.get(base + "/turns/" + payload["turn_id"]).json()["feedback"] == payload["feedback"]
    assert service_session.scalar(select(func.count()).select_from(ConversationTurn)) == 1
    assert service_session.scalar(select(func.count()).select_from(LanguageFeedback)) == 1


def test_multiturn_resume_replay_and_pagination(mocked_providers, service_session):
    client, _, llm = mocked_providers
    u, p, s = create_case(service_session, locale="en-CA")
    base = base_url(u, p, s)
    first_id = uuid.uuid4()
    sent = []
    for text, modality, rid in [("First question", "text", first_id),
                                ("Second question", "voice", uuid.uuid4()),
                                ("Third question", "text", uuid.uuid4())]:
        response = post_turn(client, base, text, modality=modality, request_id=rid)
        assert response.status_code == 201, response.text
        sent.append(response.json())
    assert [x["turn_index"] for x in sent] == [1, 2, 3]
    assert len(llm.calls) == 3
    assert any(message.content == "First question" for message in llm.calls[1][1])

    # Model a page reload / resumed session using only HTTP state.
    resumed = client.get(base)
    assert resumed.status_code == 200
    first_page = client.get(base + "/turns", params={"limit": 2, "offset": 0}).json()["items"]
    second_page = client.get(base + "/turns", params={"limit": 2, "offset": 2}).json()["items"]
    assert [x["turn_index"] for x in first_page + second_page] == [1, 2, 3]
    replay = post_turn(client, base, "First question", request_id=first_id)
    assert replay.status_code == 201 and replay.json()["replayed"] is True
    assert replay.json()["turn_id"] == sent[0]["turn_id"]
    assert len(llm.calls) == 3


def test_cross_user_and_cross_profile_do_not_leak_turns(mocked_providers, service_session):
    client, _, llm = mocked_providers
    u, p, s = create_case(service_session)
    other, other_profile, other_s = create_case(service_session, locale="en-US")
    a, b = base_url(u, p, s), base_url(other, other_profile, other_s)
    result = post_turn(client, a, "Private utterance")
    assert result.status_code == 201
    assert client.get(b + "/turns").json()["items"] == []
    cross = f"/users/{other.id}/language-profiles/{p.id}/sessions/{s.id}"
    assert client.get(cross + "/turns").status_code == 404
    assert client.get(cross + "/turns/" + result.json()["turn_id"]).status_code == 404
    assert post_turn(client, cross, "Bad access").status_code == 404
    assert len(llm.calls) == 1


def test_timeout_then_retry_succeeds_without_partial_rows(mocked_providers, service_session):
    client, _, llm = mocked_providers
    u, p, s = create_case(service_session)
    base = base_url(u, p, s)
    rid = uuid.uuid4()
    llm.exc = LLMTimeoutError("private provider detail")
    failed = post_turn(client, base, "Bonjour", request_id=rid)
    assert failed.status_code == 504 and "private" not in failed.text
    assert client.get(base + "/turns").json()["items"] == []
    assert service_session.scalar(select(func.count()).select_from(LanguageFeedback)) == 0
    llm.exc = None
    recovered = post_turn(client, base, "Bonjour", request_id=rid)
    assert recovered.status_code == 201
    assert recovered.json()["turn_index"] == 1
    assert len(client.get(base + "/turns").json()["items"]) == 1


def test_completed_session_readable_but_not_submittable(mocked_providers, service_session):
    client, _, llm = mocked_providers
    u, p, s = create_case(service_session)
    base = base_url(u, p, s)
    first = post_turn(client, base, "Bonjour")
    assert first.status_code == 201
    completed = client.post(base + "/complete")
    assert completed.status_code == 200, completed.text
    assert client.get(base + "/turns").status_code == 200
    assert client.get(base + "/turns/" + first.json()["turn_id"]).status_code == 200
    assert post_turn(client, base, "Continue").status_code == 409
    assert len(llm.calls) == 1


def test_bad_audio_and_invalid_text_are_rejected_without_provider_calls(mocked_providers, service_session):
    client, stt, llm = mocked_providers
    u, p, s = create_case(service_session)
    base = base_url(u, p, s)
    bad_audio = client.post(base + "/transcriptions", files={
        "audio": ("empty.webm", b"", "audio/webm")
    })
    assert bad_audio.status_code == 400
    invalid = post_turn(client, base, "")
    assert invalid.status_code == 422
    assert stt.calls == [] and llm.calls == []
    assert client.get(base + "/turns").json()["items"] == []
