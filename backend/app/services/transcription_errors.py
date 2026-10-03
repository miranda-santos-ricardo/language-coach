class TranscriptionError(Exception):
    """Base class for transcription errors."""

class TranscriptionSessionInactiveError(TranscriptionError):
    """Raised when a transcription session is inactive."""

class TranscriptionContextError(TranscriptionError):
    """Raised when there is an error with the transcription context."""

