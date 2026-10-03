from app.core.config import get_settings
from app.integrations.openai_stt import OpenAISpeechToText
from app.services.transcription_service import TranscriptionService


def get_transcription_service() -> TranscriptionService:
    settings = get_settings()

    speech_to_text = OpenAISpeechToText(
        api_key=settings.openai_api_key,
        model=settings.openai_stt_model,
        timeout_seconds=settings.openai_stt_timeout_seconds,
    )

    return TranscriptionService(
        speech_to_text=speech_to_text,
    )