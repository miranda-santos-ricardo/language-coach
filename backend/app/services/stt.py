from typing import BinaryIO, Protocol

class SpeechToText(Protocol):
    def transcribe(
            self,
            *,
            audio_file: BinaryIO,
            filename: str,
            content_type: str,
            language: str
    ) -> str:
        ...