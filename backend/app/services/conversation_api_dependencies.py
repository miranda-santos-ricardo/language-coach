"""Dependency factory for conversational orchestration (overridable in tests)."""
from app.services.conversation_dependencies import get_conversation_llm
from app.services.conversation_service import ConversationService


def get_conversation_service() -> ConversationService:
    return ConversationService(llm=get_conversation_llm())


from app.services.conversation_read_service import ConversationReadService


def get_conversation_read_service() -> ConversationReadService:
    """Read routes do not require a configured LLM provider."""
    return ConversationReadService()
