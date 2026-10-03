from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest

from app.models import SessionStatus
from app.services.transcription_errors import (
    TranscriptionContextError,
    TranscriptionSessionInactiveError,
)
from app.services.transcription_service import TranscriptionService
from tests.fakes.fake_stt import FakeSpeechToText


def make_practice_session(
    *,
    status: SessionStatus = SessionStatus.ACTIVE,
    variant_code: str = "fr-CA",
):
    language_variant = SimpleNamespace(
        code=variant_code,
    )

    language_profile = SimpleNamespace(
        language_variant=language_variant,
    )

    return SimpleNamespace(
        id=uuid.uuid4(),
        status=status,
        language_profile=language_profile,
    )


def make_service(
    practice_session,
    *,
    transcript: str = "Bonjour, ceci est un test.",
):
    practice_session_service = Mock()
    practice_session_service.get.return_value = practice_session

    fake_stt = FakeSpeechToText(
        transcript=transcript,
    )

    service = TranscriptionService(
        speech_to_text=fake_stt,
        practice_session_service=practice_session_service,
    )

    return service, fake_stt, practice_session_service


def call_transcribe(
    service: TranscriptionService,
    *,
    session,
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    practice_session_id: uuid.UUID,
):
    return service.transcribe(
        session=session,
        user_id=user_id,
        profile_id=profile_id,
        practice_session_id=practice_session_id,
        audio_file=BytesIO(b"fake audio"),
        filename="recording.webm",
        content_type="audio/webm",
    )


def test_transcribe_active_french_canadian_session(
    service_session,
) -> None:
    practice_session = make_practice_session(
        status=SessionStatus.ACTIVE,
        variant_code="fr-CA",
    )

    service, fake_stt, practice_session_service = make_service(
        practice_session,
        transcript="Bonjour, ceci est un test.",
    )

    user_id = uuid.uuid4()
    profile_id = uuid.uuid4()

    result = call_transcribe(
        service,
        session=service_session,
        user_id=user_id,
        profile_id=profile_id,
        practice_session_id=practice_session.id,
    )

    assert result.transcript == "Bonjour, ceci est un test."
    assert result.language == "fr"

    practice_session_service.get.assert_called_once_with(
        service_session,
        user_id,
        profile_id,
        practice_session.id,
    )

    assert len(fake_stt.calls) == 1

    call = fake_stt.calls[0]

    assert call["language"] == "fr"
    assert call["filename"] == "recording.webm"
    assert call["content_type"] == "audio/webm"


def test_transcribe_active_english_canadian_session(
    service_session,
) -> None:
    practice_session = make_practice_session(
        status=SessionStatus.ACTIVE,
        variant_code="en-CA",
    )

    service, fake_stt, _ = make_service(
        practice_session,
        transcript="This is an English transcription.",
    )

    result = call_transcribe(
        service,
        session=service_session,
        user_id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        practice_session_id=practice_session.id,
    )

    assert result.transcript == "This is an English transcription."
    assert result.language == "en"

    assert len(fake_stt.calls) == 1
    assert fake_stt.calls[0]["language"] == "en"


def test_transcribe_rejects_completed_session(
    service_session,
) -> None:
    practice_session = make_practice_session(
        status=SessionStatus.COMPLETED,
        variant_code="fr-CA",
    )

    service, fake_stt, _ = make_service(
        practice_session,
    )

    with pytest.raises(
        TranscriptionSessionInactiveError,
        match="is not active",
    ):
        call_transcribe(
            service,
            session=service_session,
            user_id=uuid.uuid4(),
            profile_id=uuid.uuid4(),
            practice_session_id=practice_session.id,
        )

    assert fake_stt.calls == []


def test_transcribe_rejects_abandoned_session(
    service_session,
) -> None:
    practice_session = make_practice_session(
        status=SessionStatus.ABANDONED,
        variant_code="fr-CA",
    )

    service, fake_stt, _ = make_service(
        practice_session,
    )

    with pytest.raises(
        TranscriptionSessionInactiveError,
        match="is not active",
    ):
        call_transcribe(
            service,
            session=service_session,
            user_id=uuid.uuid4(),
            profile_id=uuid.uuid4(),
            practice_session_id=practice_session.id,
        )

    assert fake_stt.calls == []


def test_transcribe_rejects_missing_language_variant(
    service_session,
) -> None:
    practice_session = SimpleNamespace(
        id=uuid.uuid4(),
        status=SessionStatus.ACTIVE,
        language_profile=None,
    )

    service, fake_stt, _ = make_service(
        practice_session,
    )

    with pytest.raises(
        TranscriptionContextError,
        match=f"Practice session {practice_session.id} does not have a language variant.",
    ):
        call_transcribe(
            service,
            session=service_session,
            user_id=uuid.uuid4(),
            profile_id=uuid.uuid4(),
            practice_session_id=practice_session.id,
        )

    assert fake_stt.calls == []


def test_transcribe_rejects_empty_language_variant(
    service_session,
) -> None:
    practice_session = make_practice_session(
        status=SessionStatus.ACTIVE,
        variant_code="",
    )

    service, fake_stt, _ = make_service(
        practice_session,
    )

    with pytest.raises(
        TranscriptionContextError,
        match=f"Practice session {practice_session.id} does not have a language variant.",
    ):
        call_transcribe(
            service,
            session=service_session,
            user_id=uuid.uuid4(),
            profile_id=uuid.uuid4(),
            practice_session_id=practice_session.id,
        )

    assert fake_stt.calls == []


def test_transcribe_passes_audio_metadata_to_stt(
    service_session,
) -> None:
    practice_session = make_practice_session(
        status=SessionStatus.ACTIVE,
        variant_code="fr-CA",
    )

    service, fake_stt, _ = make_service(
        practice_session,
        transcript="Transcription result.",
    )

    audio = BytesIO(
        b"some fake audio content"
    )

    result = service.transcribe(
        session=service_session,
        user_id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        practice_session_id=practice_session.id,
        audio_file=audio,
        filename="voice.webm",
        content_type="audio/webm",
    )

    assert result.transcript == "Transcription result."
    assert result.language == "fr"

    assert len(fake_stt.calls) == 1

    call = fake_stt.calls[0]

    assert call["audio_file"] is audio
    assert call["filename"] == "voice.webm"
    assert call["content_type"] == "audio/webm"
    assert call["language"] == "fr"


def test_transcribe_propagates_practice_session_service_error(
    service_session,
) -> None:
    practice_session_service = Mock()

    expected_error = RuntimeError(
        "practice session lookup failed"
    )

    practice_session_service.get.side_effect = expected_error

    fake_stt = FakeSpeechToText()

    service = TranscriptionService(
        speech_to_text=fake_stt,
        practice_session_service=practice_session_service,
    )

    with pytest.raises(RuntimeError) as exc_info:
        service.transcribe(
            session=service_session,
            user_id=uuid.uuid4(),
            profile_id=uuid.uuid4(),
            practice_session_id=uuid.uuid4(),
            audio_file=BytesIO(b"fake audio"),
            filename="recording.webm",
            content_type="audio/webm",
        )

    assert exc_info.value is expected_error
    assert fake_stt.calls == []