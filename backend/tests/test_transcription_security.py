from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.models import SessionStatus
from app.services.errors import (
    LanguageProfileNotFoundError,
    PracticeSessionNotFoundError,
    UserNotFoundError,
)
from app.services.practice_session import PracticeSessionService
from app.services.transcription_errors import (
    TranscriptionSessionInactiveError,
)
from app.services.transcription_service import TranscriptionService


def make_service(*, status=SessionStatus.ACTIVE):
    user_id = uuid4()
    profile_id = uuid4()
    practice_session_id = uuid4()

    user_repo = Mock()
    profile_repo = Mock()
    session_repo = Mock()
    stt = Mock()

    user_repo.get.return_value = SimpleNamespace(id=user_id)

    profile = SimpleNamespace(id=profile_id)
    profile_repo.get_owned.return_value = profile

    practice_session = SimpleNamespace(
        id=practice_session_id,
        status=status,
        language_profile=SimpleNamespace(
            language_variant=SimpleNamespace(code="fr-CA")
        ),
    )
    session_repo.get_owned.return_value = practice_session
    stt.transcribe.return_value = "Bonjour."

    practice_service = PracticeSessionService(
        user_repository=user_repo,
        profile_repository=profile_repo,
        practice_session_repository=session_repo,
    )

    transcription_service = TranscriptionService(
        speech_to_text=stt,
        practice_session_service=practice_service,
    )

    return SimpleNamespace(
        service=transcription_service,
        stt=stt,
        user_repo=user_repo,
        profile_repo=profile_repo,
        session_repo=session_repo,
        user_id=user_id,
        profile_id=profile_id,
        practice_session_id=practice_session_id,
    )


def transcribe(context, **overrides):
    arguments = {
        "session": Mock(),
        "user_id": context.user_id,
        "profile_id": context.profile_id,
        "practice_session_id": context.practice_session_id,
        "audio_file": BytesIO(b"fake-audio"),
        "filename": "recording.webm",
        "content_type": "audio/webm",
    }
    arguments.update(overrides)
    return context.service.transcribe(**arguments)


@pytest.mark.parametrize(
    "status",
    [SessionStatus.COMPLETED, SessionStatus.ABANDONED],
)
def test_inactive_session_never_calls_stt(status):
    context = make_service(status=status)

    with pytest.raises(TranscriptionSessionInactiveError):
        transcribe(context)

    context.stt.transcribe.assert_not_called()


def test_nonexistent_user_never_calls_stt():
    context = make_service()
    context.user_repo.get.return_value = None

    with pytest.raises(UserNotFoundError):
        transcribe(context)

    context.profile_repo.get_owned.assert_not_called()
    context.session_repo.get_owned.assert_not_called()
    context.stt.transcribe.assert_not_called()


def test_profile_not_owned_by_user_never_calls_stt():
    context = make_service()
    other_user_id = uuid4()

    context.profile_repo.get_owned.return_value = None

    with pytest.raises(LanguageProfileNotFoundError):
        transcribe(context, user_id=other_user_id)

    context.profile_repo.get_owned.assert_called_once()
    assert (
        context.profile_repo.get_owned.call_args.args[1]
        == other_user_id
    )

    context.session_repo.get_owned.assert_not_called()
    context.stt.transcribe.assert_not_called()


def test_session_not_owned_by_profile_never_calls_stt():
    context = make_service()
    other_session_id = uuid4()

    context.session_repo.get_owned.return_value = None

    with pytest.raises(PracticeSessionNotFoundError):
        transcribe(context, practice_session_id=other_session_id)

    context.session_repo.get_owned.assert_called_once()
    assert (
        context.session_repo.get_owned.call_args.args[2]
        == other_session_id
    )

    context.stt.transcribe.assert_not_called()


def test_valid_active_session_calls_stt_once():
    context = make_service()

    result = transcribe(context)

    assert result.transcript == "Bonjour."
    assert result.language == "fr"
    context.stt.transcribe.assert_called_once()