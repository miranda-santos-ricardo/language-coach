import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.services.llm import LLMResult
from app.services.structured_feedback import (
    CoachTurnOutput, FeedbackValidationError, StructuredFeedbackValidator,
)


def payload():
    dimension = {"status": "correct", "explanation": "No correction needed", "suggestion": None}
    return {
        "coach_response": "Très bien. Pouvez-vous préciser votre argument?",
        "feedback": {
            "overall_assessment": "Clearly formulated",
            "grammar": deepcopy(dimension), "vocabulary": deepcopy(dimension),
            "clarity": deepcopy(dimension), "naturalness": deepcopy(dimension),
            "register": deepcopy(dimension),
            "improved_version": "Je voudrais présenter cette solution à mon directeur.",
            "explanations": [], "strengths": ["Clear intention"],
            "next_recommendation": "Explain the benefits",
        },
    }


def validate(p):
    return StructuredFeedbackValidator().validate(LLMResult(content=json.dumps(p), model="fake"))


def test_valid_fr_ca_response_and_persistence_mapping():
    output = validate(payload())
    assert isinstance(output, CoachTurnOutput)
    assert output.feedback.grammar.status == "correct"
    assert output.feedback.grammar.model_dump()["status"] == "correct"
    assert output.feedback.strengths == ["Clear intention"]


def test_valid_professional_improvement_without_marking_error():
    p = payload()
    p["feedback"]["register"] = {"status": "improvement_possible", "explanation": "More formal option", "suggestion": "Je souhaiterais…"}
    assert validate(p).feedback.register_feedback.status == "improvement_possible"


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(coach_response="  "),
    lambda p: p.update(unexpected="value"),
    lambda p: p["feedback"].pop("register"),
    lambda p: p["feedback"]["grammar"].update(status="maybe"),
    lambda p: p["feedback"]["grammar"].update(status="incorrect", suggestion=None),
    lambda p: p["feedback"].update(strengths=[]),
    lambda p: p["feedback"].update(strengths=[" \t"]),
    lambda p: p["feedback"].update(improved_version=" \n "),
    lambda p: p["feedback"].update(overall_assessment=12),
    lambda p: p["feedback"].update(explanations=["x"] * 9),
    lambda p: p["feedback"]["grammar"].update(extra="field"),
])
def test_invalid_output_rejected(mutation):
    p = payload()
    mutation(p)
    with pytest.raises(FeedbackValidationError, match="invalid structured feedback"):
        validate(p)


@pytest.mark.parametrize("raw", [
    "", "not JSON", "[]", "null", "{", '{"coach_response":"a","coach_response":"b"}', " " * 24001,
])
def test_invalid_json_never_fabricates_feedback(raw):
    with pytest.raises(FeedbackValidationError):
        StructuredFeedbackValidator().validate(LLMResult(content=raw, model="fake"))


def test_error_does_not_expose_provider_text():
    with pytest.raises(FeedbackValidationError) as error:
        StructuredFeedbackValidator().validate(LLMResult(content="PRIVATE PROVIDER MESSAGE", model="fake"))
    assert "PRIVATE" not in str(error.value)


def test_model_refuses_non_json_strict_types():
    with pytest.raises(ValidationError):
        CoachTurnOutput.model_validate({**payload(), "coach_response": 123})
