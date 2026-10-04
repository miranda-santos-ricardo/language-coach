import pytest

from app.services.audio_upload import (
    DEFAULT_MAX_AUDIO_SIZE_BYTES,
    validate_audio_upload,
)
from app.services.audio_upload_errors import (
    AudioFileTooLargeError,
    EmptyAudioFileError,
    UnsupportedAudioTypeError,
)


def test_validate_audio_upload_accepts_webm() -> None:
    content = b"fake webm audio"

    result = validate_audio_upload(
        content=content,
        filename="recording.webm",
        content_type="audio/webm",
    )

    assert result.content == content
    assert result.filename == "recording.webm"
    assert result.content_type == "audio/webm"


def test_validate_audio_upload_accepts_mp4() -> None:
    result = validate_audio_upload(
        content=b"fake mp4 audio",
        filename="recording.mp4",
        content_type="audio/mp4",
    )

    assert result.filename == "recording.mp4"
    assert result.content_type == "audio/mp4"


def test_validate_audio_upload_accepts_mpeg() -> None:
    result = validate_audio_upload(
        content=b"fake mp3 audio",
        filename="recording.mp3",
        content_type="audio/mpeg",
    )

    assert result.filename == "recording.mp3"
    assert result.content_type == "audio/mpeg"


def test_validate_audio_upload_accepts_wav() -> None:
    result = validate_audio_upload(
        content=b"fake wav audio",
        filename="recording.wav",
        content_type="audio/wav",
    )

    assert result.filename == "recording.wav"
    assert result.content_type == "audio/wav"


def test_validate_audio_upload_rejects_empty_audio() -> None:
    with pytest.raises(
        EmptyAudioFileError,
        match="Uploaded audio file is empty",
    ):
        validate_audio_upload(
            content=b"",
            filename="recording.webm",
            content_type="audio/webm",
        )


def test_validate_audio_upload_rejects_unsupported_content_type() -> None:
    with pytest.raises(
        UnsupportedAudioTypeError,
        match="Unsupported audio content type",
    ):
        validate_audio_upload(
            content=b"not really audio",
            filename="recording.ogg",
            content_type="audio/ogg",
        )


def test_validate_audio_upload_rejects_missing_content_type() -> None:
    with pytest.raises(
        UnsupportedAudioTypeError,
        match="Unsupported audio content type",
    ):
        validate_audio_upload(
            content=b"audio",
            filename="recording.webm",
            content_type=None,
        )


def test_validate_audio_upload_rejects_file_above_max_size() -> None:
    max_size = 10

    with pytest.raises(
        AudioFileTooLargeError,
        match="exceeds the maximum allowed size",
    ):
        validate_audio_upload(
            content=b"x" * 11,
            filename="recording.webm",
            content_type="audio/webm",
            max_size_bytes=max_size,
        )


def test_validate_audio_upload_accepts_file_at_exact_max_size() -> None:
    max_size = 10
    content = b"x" * max_size

    result = validate_audio_upload(
        content=content,
        filename="recording.webm",
        content_type="audio/webm",
        max_size_bytes=max_size,
    )

    assert result.content == content
    assert len(result.content) == max_size


def test_validate_audio_upload_uses_default_filename_when_missing() -> None:
    result = validate_audio_upload(
        content=b"audio",
        filename=None,
        content_type="audio/webm",
    )

    assert result.filename == "recording.webm"


def test_default_audio_upload_limit_is_10_mb() -> None:
    assert DEFAULT_MAX_AUDIO_SIZE_BYTES == 10 * 1024 * 1024


#Normalized audio test
from app.services.audio_upload import (
    normalize_audio_content_type,
    validate_audio_upload,
)

def test_accepts_webm_with_opus_codec_parameter():
    result = validate_audio_upload(
        content=b"audio-data",
        filename="recording.webm",
        content_type="audio/webm;codecs=opus",
    )

    assert result.content == b"audio-data"
    assert result.filename == "recording.webm"
    assert result.content_type == "audio/webm"

def test_normalizes_audio_content_type():
    assert (
        normalize_audio_content_type("audio/webm;codecs=opus")
        == "audio/webm"
    )

def test_normalizes_audio_content_type_case_and_whitespace():
    assert (
        normalize_audio_content_type(
            " Audio/WebM ; codecs=opus "
        )
        == "audio/webm"
    )