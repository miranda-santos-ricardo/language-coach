"""Provider-neutral conversational inference contract (no prompt generation)."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMMessage:
    role: str  # user or assistant; trusted system instructions are separate
    content: str


@dataclass(frozen=True)
class LLMResult:
    content: str  # raw provider JSON; validated by the feedback layer in Step 5
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class ConversationLLM(Protocol):
    def generate(self, *, instructions: str, messages: list[LLMMessage]) -> LLMResult:
        ...
