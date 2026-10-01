class STTError(Exception):
    """Base exception for speech-to-text failures."""


class STTConfigurationError(STTError):
    """Speech-to-text is not correctly configured."""


class STTTimeoutError(STTError):
    """Speech-to-text provider timed out."""


class STTRateLimitError(STTError):
    """Speech-to-text provider rate limit was reached."""


class STTProviderError(STTError):
    """Speech-to-text provider failed."""