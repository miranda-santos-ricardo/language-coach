from dataclasses import dataclass
from app.services.audio_upload_errors import (
    AudioUploadError,
    EmptyAudioFileError,    
    UnsupportedAudioTypeError,
    AudioFileTooLargeError
)


SUPPORTED_AUDIO_TYPES = {
    "audio/webm",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/m4a",
}

DEFAULT_MAX_AUDIO_SIZE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class ValidatedAudio:
    content: bytes
    filename: str
    content_type: str


def validate_audio_upload(
    *,
    content: bytes,
    filename: str | None,
    content_type: str | None,
    max_size_bytes: int = DEFAULT_MAX_AUDIO_SIZE_BYTES,
) -> ValidatedAudio:
    if not content:
        raise EmptyAudioFileError(
            "Uploaded audio file is empty."
        )

    if content_type not in SUPPORTED_AUDIO_TYPES:
        raise UnsupportedAudioTypeError(
            f"Unsupported audio content type: {content_type}"
        )

    if len(content) > max_size_bytes:
        raise AudioFileTooLargeError(
            "Uploaded audio file exceeds the maximum allowed size."
        )

    safe_filename = filename or "recording.webm"

    return ValidatedAudio(
        content=content,
        filename=safe_filename,
        content_type=content_type,
    )