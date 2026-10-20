"""Conservative QL-001 consistency signal for tests/evaluation, not a language judge.

Does not automatically rewrite, reject, or persist provider feedback. A concrete
suggestion may not require a full-sentence rewrite in every pedagogical setting.
"""
from dataclasses import dataclass
import unicodedata

from app.services.structured_feedback import CoachTurnOutput


@dataclass(frozen=True)
class FeedbackConsistencyFinding:
    code: str
    dimension: str


def _canonical(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def evaluate_feedback_consistency(
    *, learner_text: str, output: CoachTurnOutput, training_mode: str,
    communication_register: str,
) -> tuple[FeedbackConsistencyFinding, ...]:
    """Flag obvious unchanged improved_version in a professional context.

    This intentionally cannot prove semantic alignment or linguistic quality.
    """
    professional = (training_mode == "professional" or
                    communication_register in {"professional", "formal", "formal_executive"})
    if not professional:
        return ()
    reg = output.feedback.register_feedback
    if (reg.status == "improvement_possible" and reg.suggestion and
            _canonical(learner_text) == _canonical(output.feedback.improved_version)):
        return (FeedbackConsistencyFinding(
            code="professional_register_suggestion_not_reflected", dimension="register"
        ),)
    return ()
