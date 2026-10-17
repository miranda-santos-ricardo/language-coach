"""Bounded quality-evaluation runner. Dry-run is the safe default.

Automated checks compare output to human-authored *expectations*; subjective
linguistic quality remains explicitly unscored pending human review.
"""
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.evaluation.deterministic import evaluate_output
from app.services.conversation_context import ConversationContext
from app.services.conversation_prompt import ConversationPromptBuilder
from app.services.llm import ConversationLLM, LLMMessage, LLMResult
from app.services.structured_feedback import FeedbackValidationError, StructuredFeedbackValidator


@dataclass(frozen=True)
class QualityRunSettings:
    mode: str = "dry-run"
    max_cases: int = 14

    def __post_init__(self):
        if self.mode not in ("dry-run", "live"):
            raise ValueError("Unsupported evaluation mode")
        if not 1 <= self.max_cases <= 50:
            raise ValueError("max_cases must be between 1 and 50")


def case_context(case: dict[str, Any]) -> ConversationContext:
    """Build evaluation context from *versioned fixtures*, never DB user data."""
    locale = case["language_variant"]
    language = "French" if locale.lower().startswith("fr") else "English"
    return ConversationContext(
        language_variant=locale,
        language_name=language,
        current_cefr=case["cefr"],
        target_cefr=None,
        training_mode=case["training_mode"],
        communication_register=case["register"],
        scenario_key=None,
        recent_messages=(),
    )


def run_quality_evaluation(
    cases: list[dict[str, Any]], *, settings: QualityRunSettings,
    provider: ConversationLLM | None = None,
    live_authorized: bool = False,
) -> dict[str, Any]:
    """In live mode the caller must supply both authorization and a provider.

    The provider is not created or imported here. Never instantiate a real
    client before the explicit live-mode checks have succeeded.
    """
    if settings.mode == "live" and (not live_authorized or provider is None):
        raise PermissionError("Live evaluation requires explicit authorization and provider")
    selected = cases[:settings.max_cases]
    prompt_builder = ConversationPromptBuilder()
    validator = StructuredFeedbackValidator()
    entries = []
    for case in selected:
        prompt = prompt_builder.build(case_context(case))
        started = perf_counter()
        result: LLMResult | None = None
        try:
            if settings.mode == "dry-run":
                import json
                result = LLMResult(content=json.dumps(case["reference_output"], ensure_ascii=False), model="synthetic-fixture")
            else:
                assert provider is not None
                result = provider.generate(
                    instructions=prompt.instructions,
                    messages=[LLMMessage(role="user", content=case["learner_text"])],
                )
            # Validate using the exact application contract.
            validator.validate(result)
            evaluation = evaluate_output(case, result.content)
            checks = list(evaluation.failures)
            status = "pass" if not checks else "fail"
            error_type = None
        except FeedbackValidationError:
            checks, status, error_type = ["invalid_schema"], "fail", "invalid_schema"
        except Exception:
            # No provider text, secrets, or learner content in the report.
            checks, status, error_type = ["provider_or_runtime_error"], "error", "provider_or_runtime_error"
        elapsed = round((perf_counter() - started) * 1000, 2)
        entries.append({
            "case_id": case["id"], "category": case["category"], "locale": case["language_variant"],
            "cefr": case["cefr"], "status": status, "failures": checks,
            "prompt_version": prompt.version, "model": result.model if result else None,
            "latency_ms": elapsed if settings.mode == "live" else None,
            "input_tokens": result.input_tokens if result else None,
            "output_tokens": result.output_tokens if result else None,
            "error_category": error_type,
            "human_review_required": settings.mode == "live",
            "subjective_quality": "not_assessed",
        })
    return {
        "mode": settings.mode,
        "dataset_version": "phase5-eval-v1", "total": len(entries),
        "passed": sum(e["status"] == "pass" for e in entries),
        "failed": sum(e["status"] == "fail" for e in entries),
        "errors": sum(e["status"] == "error" for e in entries),
        "cases": entries,
        "disclaimer": "Automatic checks are not proof of linguistic quality, CEFR accuracy, or prompt-injection resistance. Live runs require human review.",
    }
