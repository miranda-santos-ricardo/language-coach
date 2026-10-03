from __future__ import annotations

import uuid
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.models import SessionStatus
from app.schemas.transcription import TranscriptionResult
from app.services.practice_session import PracticeSessionService
from app.services.stt import SpeechToText
from app.services.stt_language import to_stt_language
from app.services.transcription_errors import(
    TranscriptionContextError,
    TranscriptionSessionInactiveError,
)


class TranscriptionService:
    def __init__(
            self,
            *,
            speech_to_text: SpeechToText,
            practice_session_service: PracticeSessionService | None = None,
    ) -> None:
        self._speech_to_text = speech_to_text
        self._practice_session_service = (
            practice_session_service or PracticeSessionService()
        )


    def transcribe(
            self,
            *,
            session: Session,
            user_id:uuid.UUID,
            profile_id:uuid.UUID,
            practice_session_id:uuid.UUID,
            audio_file: BinaryIO,
            filename: str,
            content_type: str,
    ) -> TranscriptionResult:
        """
        Transcribe an audio file for a given practice session.

        Args:
            session (Session): The SQLAlchemy session.
            user_id (uuid.UUID): The ID of the user.
            profile_id (uuid.UUID): The ID of the profile.
            practice_session_id (uuid.UUID): The ID of the practice session.
            audio_file (BinaryIO): The audio file to transcribe.
            filename (str): The name of the audio file.
            content_type (str): The content type of the audio file.
        """
        practice_session = self._practice_session_service.get(
            session,
            user_id,
            profile_id,
            practice_session_id
        )

        self._require_active(practice_session)

        locale = self._get_locale(practice_session)
        language = to_stt_language(locale)

        transcript = self._speech_to_text.transcribe(
            audio_file=audio_file,
            filename=filename,
            content_type=content_type,
            language=language
        )

        return TranscriptionResult(
            transcript=transcript,
            language=language,
        )

    @staticmethod
    def _require_active(practice_session) -> None:
        if practice_session.status != SessionStatus.ACTIVE:
            raise TranscriptionSessionInactiveError(
                f"Practice session {practice_session.id} is not active."
            )

    @staticmethod
    def _get_locale(practice_session) -> str:
        try:
            locale = practice_session.language_profile.language_variant.code
        except AttributeError as exc:
            raise TranscriptionContextError(
                f"Practice session {practice_session.id} does not have a language variant."
            ) from exc

        if not locale:
            raise TranscriptionContextError(
                f"Practice session {practice_session.id} does not have a language variant."
            )

        return locale