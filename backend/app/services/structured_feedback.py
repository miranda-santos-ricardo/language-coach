"""Phase 5 Step 5: strict provider-output contract, independent of any SDK.

No database writes or model calls happen in this module.
"""
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.services.llm import LLMResult


class FeedbackValidationError(Exception):
    """Provider content does not satisfy the conversational feedback contract."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class FeedbackDimension(StrictModel):
    status: Literal["correct", "improvement_possible", "incorrect", "not_applicable"]
    explanation: str = Field(min_length=1, max_length=1200)
    suggestion: str | None = Field(min_length=1, max_length=1200)

    @field_validator("explanation", "suggestion")
    @classmethod
    def strip_and_reject_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Feedback fields cannot be whitespace-only")
        return value

    @model_validator(mode="after")
    def require_suggestion_for_issue(self):
        if self.status == "incorrect" and self.suggestion is None:
            raise ValueError("Incorrect feedback needs a suggested correction")
        return self


class StructuredLanguageFeedback(StrictModel):
    overall_assessment: str = Field(min_length=1, max_length=1500)
    grammar: FeedbackDimension
    vocabulary: FeedbackDimension
    clarity: FeedbackDimension
    naturalness: FeedbackDimension
    register_feedback: FeedbackDimension = Field(alias="register")
    improved_version: str = Field(min_length=1, max_length=4000)
    explanations: list[str] = Field(max_length=8)
    strengths: list[str] = Field(min_length=1, max_length=8)
    next_recommendation: str = Field(min_length=1, max_length=1200)

    @field_validator("overall_assessment", "improved_version", "next_recommendation")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Feedback text cannot be blank")
        return value

    @field_validator("explanations", "strengths")
    @classmethod
    def validate_items(cls, value: list[str]) -> list[str]:
        clean = []
        for item in value:
            if not isinstance(item, str) or not item.strip() or len(item) > 1000:
                raise ValueError("Feedback list items must be nonempty text of at most 1000 characters")
            clean.append(item.strip())
        return clean


class CoachTurnOutput(StrictModel):
    coach_response: str = Field(min_length=1, max_length=4000)
    feedback: StructuredLanguageFeedback

    @field_validator("coach_response")
    @classmethod
    def nonblank_response(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Coach response cannot be blank")
        return value


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


class StructuredFeedbackValidator:
    """Parse and strictly validate a provider result without inventing fallback feedback."""

    def validate(self, result: LLMResult) -> CoachTurnOutput:
        if not isinstance(result.content, str) or not result.content.strip():
            raise FeedbackValidationError("Provider returned invalid structured feedback")
        if len(result.content) > 24000:
            raise FeedbackValidationError("Provider returned invalid structured feedback")
        try:
            payload = json.loads(result.content, object_pairs_hook=_unique_keys)
            return CoachTurnOutput.model_validate(payload)
        except (ValueError, TypeError, ValidationError) as exc:
            raise FeedbackValidationError("Provider returned invalid structured feedback") from exc
