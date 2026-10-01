import pytest 

from app.integrations.openai_stt import OpenAISpeechToText
from app.services.stt_errors import STTConfigurationError

def test_openai_stt_requires_api_key() -> None:
    with pytest.raises(
        STTConfigurationError,
        match="OpenAI API key is not configured."
    ):
        OpenAISpeechToText(api_key=None)