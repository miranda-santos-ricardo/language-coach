"""OpenAI Chat Completions adapter; prompts and feedback parsing live elsewhere."""
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from app.services.llm import LLMMessage, LLMResult
from app.services.llm_errors import (
    LLMConfigurationError, LLMProviderError, LLMRateLimitError, LLMTimeoutError,
)


class OpenAIConversationLLM:
    def __init__(self, *, api_key: str | None, model: str = "gpt-4o-mini", timeout_seconds: float = 30.0, client=None) -> None:
        if not api_key or not api_key.strip():
            raise LLMConfigurationError("LLM API key is not configured.")
        if not model.strip() or timeout_seconds <= 0:
            raise LLMConfigurationError("Invalid LLM model or timeout configuration.")
        self._model = model
        self._client = client if client is not None else OpenAI(api_key=api_key, timeout=timeout_seconds)

    def generate(self, *, instructions: str, messages: list[LLMMessage]) -> LLMResult:
        if not instructions.strip() or not messages:
            raise ValueError("Instructions and at least one message are required.")
        if any(m.role not in ("user", "assistant") or not m.content.strip() for m in messages):
            raise ValueError("Only nonempty user/assistant messages are allowed.")
        if messages[-1].role != "user":
            raise ValueError("Final message must be from learner.")
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "system", "content": instructions}] + [
                    {"role": item.role, "content": item.content} for item in messages
                ],
                response_format={"type": "json_object"},
            )
        except APITimeoutError as exc:
            raise LLMTimeoutError("Conversation provider timed out.") from exc
        except RateLimitError as exc:
            raise LLMRateLimitError("Conversation provider rate limit reached.") from exc
        except (APIConnectionError, APIStatusError) as exc:
            raise LLMProviderError("Conversation provider request failed.") from exc
        except Exception as exc:
            # No raw SDK detail is allowed through this boundary.
            raise LLMProviderError("Conversation provider request failed.") from exc

        try:
            content = response.choices[0].message.content
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Empty content")
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", None)
            output_tokens = getattr(usage, "completion_tokens", None)
            return LLMResult(
                content=content, model=getattr(response, "model", None) or self._model,
                input_tokens=input_tokens, output_tokens=output_tokens,
            )
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            raise LLMProviderError("Conversation provider returned unusable content.") from exc
