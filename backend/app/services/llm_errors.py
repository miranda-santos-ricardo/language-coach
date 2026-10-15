"""Safe application-level error categories: no provider payloads in messages."""
class LLMError(Exception):
    """Base conversational inference error."""


class LLMConfigurationError(LLMError):
    """Missing or invalid provider configuration."""


class LLMTimeoutError(LLMError):
    """Provider request timed out."""


class LLMRateLimitError(LLMError):
    """Provider rate limit reached."""


class LLMProviderError(LLMError):
    """Provider unavailable or response unusable."""
