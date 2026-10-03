from typing import BinaryIO


class FakeSpeechToText:
    def __init__(self, transcript: str = "Bonjour, ceci est un test.") -> None:
        self.transcript = transcript
        self.calls: list[dict[str, object]] = []

    def transcribe(
        self,
        *,
        audio_file: BinaryIO,
        filename: str,
        content_type: str,
        language: str,
    ) -> str:
        self.calls.append(
            {
                "audio_file": audio_file,
                "filename": filename,
                "content_type": content_type,
                "language": language,
            }
        )

        return self.transcript