"""Compose provider at the application boundary; no network call on construction."""
from app.core.config import get_settings
from app.integrations.openai_conversation import OpenAIConversationLLM


def get_conversation_llm() -> OpenAIConversationLLM:
    settings = get_settings()
    return OpenAIConversationLLM(
        api_key=settings.openai_api_key,
        model=settings.openai_conversation_model,
        timeout_seconds=settings.openai_conversation_timeout_seconds,
    )
