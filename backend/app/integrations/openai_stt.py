from typing import BinaryIO

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError
)

from app.services.stt_errors import (
    STTConfigurationError,
    STTProviderError,
    STTRateLimitError,
    STTTimeoutError
)

class OpenAISpeechToText:
    def __init__(
            self, 
            *,
            api_key: str | None,
            model: str = "gpt-transcribe",
            timeout_seconds: float = 30.0
    ) -> None:
        if not api_key:
            raise STTConfigurationError(
                "OpenAI API key is not configured."
            )

        self._model = model
        self._client = OpenAI(
            api_key=api_key,

        )

    def transcribe(
            self,
            *,
            audio_file: BinaryIO,
            filename: str,
            content_type: str,
            language: str
    ) -> str:
        try:
            transcription = self._client.audio.transcriptions.create(
                model = self._model,
                file=(filename, audio_file, content_type),
                extra_body={
                    "languages": [language]
                }
            )
        except APITimeoutError as exc:
            raise STTTimeoutError("OpenAI transcription timed out.") from exc
        except RateLimitError as exc:
            raise STTRateLimitError("OpenAI transcriptions rate limit reached.") from exc
        except (APIConnectionError, APIStatusError) as exc:
            raise STTProviderError("OpenAI transcription failed.") from exc

        transcript = transcription.text.strip()

        if not transcript:
            raise STTProviderError("OpenAI returned an empty transcription.")

        return transcript
        
        