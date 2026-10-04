from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import practice_sessions
from app.schemas.transcription import TranscriptionResult


class FakeTranscriptionService:
    def __init__(
        self,
        *,
        transcript: str = "Bonjour, je voudrais pratiquer mon français.",
        language: str = "fr",
    ) -> None:
        self.transcript = transcript
        self.language = language
        self.calls: list[dict] = []

    def transcribe(
        self,
        *,
        session,
        user_id,
        profile_id,
        practice_session_id,
        audio_file,
        filename,
        content_type,
    ) -> TranscriptionResult:
        content = audio_file.read()

        self.calls.append(
            {
                "session": session,
                "user_id": user_id,
                "profile_id": profile_id,
                "practice_session_id": practice_session_id,
                "content": content,
                "filename": filename,
                "content_type": content_type,
            }
        )

        return TranscriptionResult(
            transcript=self.transcript,
            language=self.language,
        )


def transcription_url(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    practice_session_id: uuid.UUID,
) -> str:
    return (
        f"/users/{user_id}"
        f"/language-profiles/{profile_id}"
        f"/sessions/{practice_session_id}"
        "/transcriptions"
    )


def test_transcription_endpoint_accepts_multipart_audio(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    practice_session_id = uuid.uuid4()

    fake_service = FakeTranscriptionService()

    monkeypatch.setattr(
        practice_sessions,
        "get_transcription_service",
        lambda: fake_service,
    )

    response = api_client.post(
        transcription_url(
            user_id,
            profile_id,
            practice_session_id,
        ),
        files={
            "audio": (
                "recording.webm",
                b"fake-webm-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "transcript": "Bonjour, je voudrais pratiquer mon français.",
        "language": "fr",
    }

    assert len(fake_service.calls) == 1

    call = fake_service.calls[0]

    assert call["user_id"] == user_id
    assert call["profile_id"] == profile_id
    assert call["practice_session_id"] == practice_session_id
    assert call["content"] == b"fake-webm-audio"
    assert call["filename"] == "recording.webm"
    assert call["content_type"] == "audio/webm"


def test_transcription_endpoint_supports_english_result(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    practice_session_id = uuid.uuid4()

    fake_service = FakeTranscriptionService(
        transcript="I would like to practice my English.",
        language="en",
    )

    monkeypatch.setattr(
        practice_sessions,
        "get_transcription_service",
        lambda: fake_service,
    )

    response = api_client.post(
        transcription_url(
            user_id,
            profile_id,
            practice_session_id,
        ),
        files={
            "audio": (
                "recording.webm",
                b"fake-english-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "transcript": "I would like to practice my English.",
        "language": "en",
    }


def test_transcription_endpoint_rejects_empty_audio(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FakeTranscriptionService()

    monkeypatch.setattr(
        practice_sessions,
        "get_transcription_service",
        lambda: fake_service,
    )

    response = api_client.post(
        transcription_url(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        ),
        files={
            "audio": (
                "recording.webm",
                b"",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 400
    assert fake_service.calls == []


def test_transcription_endpoint_rejects_unsupported_audio_type(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FakeTranscriptionService()

    monkeypatch.setattr(
        practice_sessions,
        "get_transcription_service",
        lambda: fake_service,
    )

    response = api_client.post(
        transcription_url(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        ),
        files={
            "audio": (
                "recording.ogg",
                b"fake-ogg-audio",
                "audio/ogg",
            )
        },
    )

    assert response.status_code == 415
    assert fake_service.calls == []


def test_transcription_endpoint_requires_audio_field(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FakeTranscriptionService()

    monkeypatch.setattr(
        practice_sessions,
        "get_transcription_service",
        lambda: fake_service,
    )

    response = api_client.post(
        transcription_url(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        ),
    )

    assert response.status_code == 422
    assert fake_service.calls == []


#Step 6.3 — Error → HTTP Mapping
from app.services.audio_upload import DEFAULT_MAX_AUDIO_SIZE_BYTES
from app.services.errors import (
    LanguageProfileNotFoundError,
    PracticeSessionNotFoundError,
    UserNotFoundError,
)
from app.services.stt_errors import (
    STTConfigurationError,
    STTProviderError,
    STTRateLimitError,
    STTTimeoutError,
)
from app.services.transcription_errors import (
    TranscriptionSessionInactiveError,
)

class FailingTranscriptionService:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def transcribe(self, **kwargs):
        self.calls += 1
        raise self.error

#6.3.2 — 404 para User inexistente
def test_transcription_endpoint_returns_404_when_user_not_found(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FailingTranscriptionService(
        UserNotFoundError("User not found.")
    )

    monkeypatch.setattr(
        practice_sessions,
        "get_transcription_service",
        lambda: fake_service,
    )

    response = api_client.post(
        transcription_url(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        ),
        files={
            "audio": (
                "recording.webm",
                b"fake-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 404
    assert fake_service.calls == 1

#6.3.3 — 404 para Profile inexistente
def test_transcription_endpoint_returns_404_when_profile_not_found(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FailingTranscriptionService(
        LanguageProfileNotFoundError("Language profile not found.")
    )

    monkeypatch.setattr(
        practice_sessions,
        "get_transcription_service",
        lambda: fake_service,
    )

    response = api_client.post(
        transcription_url(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        ),
        files={
            "audio": (
                "recording.webm",
                b"fake-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 404
    assert fake_service.calls == 1

#6.3.4 — 404 para PracticeSession inexistente
def test_transcription_endpoint_returns_404_when_session_not_found(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FailingTranscriptionService(
        PracticeSessionNotFoundError("Practice session not found.")
    )

    monkeypatch.setattr(
        practice_sessions,
        "get_transcription_service",
        lambda: fake_service,
    )

    response = api_client.post(
        transcription_url(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        ),
        files={
            "audio": (
                "recording.webm",
                b"fake-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 404
    assert fake_service.calls == 1

#6.3.5 — 409 para sessão inativa
@pytest.mark.parametrize(
    "message",
    [
        "Practice session is completed.",
        "Practice session is abandoned.",
    ],
)
def test_transcription_endpoint_returns_409_when_session_is_inactive(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    message: str,
) -> None:
    fake_service = FailingTranscriptionService(
        TranscriptionSessionInactiveError(message)
    )

    monkeypatch.setattr(
        practice_sessions,
        "get_transcription_service",
        lambda: fake_service,
    )

    response = api_client.post(
        transcription_url(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        ),
        files={
            "audio": (
                "recording.webm",
                b"fake-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 409
    assert fake_service.calls == 1

#6.3.6 — 413 para arquivo acima do limite
def test_transcription_endpoint_returns_413_when_audio_is_too_large(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FakeTranscriptionService()

    monkeypatch.setattr(
        practice_sessions,
        "get_transcription_service",
        lambda: fake_service,
    )

    response = api_client.post(
        transcription_url(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        ),
        files={
            "audio": (
                "recording.webm",
                b"x" * (DEFAULT_MAX_AUDIO_SIZE_BYTES + 1),
                "audio/webm",
            )
        },
    )

    assert response.status_code == 413
    assert fake_service.calls == []

#6.3.7 — 503 para configuração OpenAI ausente
def test_transcription_endpoint_returns_503_on_stt_configuration_error(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FailingTranscriptionService(
        STTConfigurationError("OPENAI_API_KEY is missing.")
    )

    monkeypatch.setattr(
        practice_sessions,
        "get_transcription_service",
        lambda: fake_service,
    )

    response = api_client.post(
        transcription_url(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        ),
        files={
            "audio": (
                "recording.webm",
                b"fake-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 503

    # Internal provider/configuration details must not leak.
    assert "OPENAI_API_KEY" not in response.text

#6.3.8 — 503 para rate limit
def test_transcription_endpoint_returns_503_on_stt_rate_limit(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FailingTranscriptionService(
        STTRateLimitError("OpenAI rate limit exceeded.")
    )

    monkeypatch.setattr(
        practice_sessions,
        "get_transcription_service",
        lambda: fake_service,
    )

    response = api_client.post(
        transcription_url(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        ),
        files={
            "audio": (
                "recording.webm",
                b"fake-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 503
    assert "rate limit" not in response.text.lower()

#6.3.9 — 503 para provider failure
def test_transcription_endpoint_returns_503_on_stt_provider_error(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FailingTranscriptionService(
        STTProviderError("Internal provider failure.")
    )

    monkeypatch.setattr(
        practice_sessions,
        "get_transcription_service",
        lambda: fake_service,
    )

    response = api_client.post(
        transcription_url(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        ),
        files={
            "audio": (
                "recording.webm",
                b"fake-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 503
    assert "Internal provider failure" not in response.text

#6.3.10 — 504 para timeout
def test_transcription_endpoint_returns_504_on_stt_timeout(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_service = FailingTranscriptionService(
        STTTimeoutError("Provider request timed out.")
    )

    monkeypatch.setattr(
        practice_sessions,
        "get_transcription_service",
        lambda: fake_service,
    )

    response = api_client.post(
        transcription_url(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
        ),
        files={
            "audio": (
                "recording.webm",
                b"fake-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 504
    assert "Provider request timed out" not in response.text
