"""Deterministic offline evaluation; never calls an LLM, DB, or remote service.

Synthetic fixture expectations are *contract checks*, not proof of linguistic
correctness or proof that a real provider will follow prompts.
"""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from app.services.llm import LLMResult
from app.services.structured_feedback import FeedbackValidationError, StructuredFeedbackValidator

DATASET_VERSION = "phase5-eval-v1"
DIMENSIONS = ("grammar", "vocabulary", "clarity", "naturalness", "register")
STATUSES = frozenset({"correct", "incorrect", "improvement_possible", "not_applicable"})
LEVELS = frozenset({"A1", "A2", "B1", "B2", "C1", "C2"})


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    passed: bool
    failures: tuple[str, ...]


def load_dataset(path: Path) -> list[dict[str, Any]]:
    """Read and sanity-check a versioned JSON evaluation dataset."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("version") != DATASET_VERSION:
        raise ValueError("Unexpected evaluation dataset version")
    cases = doc.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation dataset must contain cases")
    ids = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Malformed evaluation case")
        required = ("id", "language_variant", "cefr", "training_mode", "register", "learner_text", "category", "expected_statuses", "reference_output")
        if any(k not in case for k in required):
            raise ValueError("Missing required evaluation case property")
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id or case_id in ids:
            raise ValueError("Duplicate or invalid evaluation case id")
        ids.add(case_id)
        if case["cefr"] not in LEVELS or not isinstance(case["learner_text"], str) or not case["learner_text"].strip():
            raise ValueError("Invalid CEFR or learner text")
        if not isinstance(case["expected_statuses"], dict) or any(
            k not in DIMENSIONS or v not in STATUSES for k, v in case["expected_statuses"].items()
        ) or not case["expected_statuses"]:
            raise ValueError("Invalid expected statuses")
        if case["training_mode"] not in ("general", "professional"):
            raise ValueError("Invalid training mode")
        if not isinstance(case["language_variant"], str) or not case["language_variant"].strip():
            raise ValueError("Invalid locale")
    return cases


def evaluate_output(case: dict[str, Any], payload: dict[str, Any] | str) -> EvaluationResult:
    """Evaluate a fixture or supplied output against objective checks.

    Status assertions are annotated test-case expectations, not an independent
    assessment of whether the language was correctly judged.
    """
    failures: list[str] = []
    raw = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    try:
        output = StructuredFeedbackValidator().validate(LLMResult(content=raw, model="offline-fixture"))
    except FeedbackValidationError:
        return EvaluationResult(case_id=case["id"], passed=False, failures=("invalid_schema",))
    for field, expected in case["expected_statuses"].items():
        dimension = output.feedback.register_feedback if field == "register" else getattr(output.feedback, field)
        if dimension.status != expected:
            failures.append(f"status_mismatch:{field}")
    if case["category"] == "prompt_injection":
        # Objective forbidden markers set by fixture; this is a narrow canary,
        # NOT a complete prompt-injection security assessment.
        lower = (output.coach_response + " " + output.feedback.overall_assessment).lower()
        for marker in case.get("forbidden_markers", []):
            if marker.lower() in lower:
                failures.append("forbidden_marker_present")
                break
    if case["category"] == "regional_valid" and output.feedback.grammar.status == "incorrect":
        failures.append("regional_grammar_false_positive_fixture")
    return EvaluationResult(case_id=case["id"], passed=not failures, failures=tuple(failures))


def evaluate_dataset(cases: list[dict[str, Any]]) -> list[EvaluationResult]:
    return [evaluate_output(c, c["reference_output"]) for c in cases]
