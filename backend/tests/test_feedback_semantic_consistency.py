"""QL-001 regression tests: zero network calls, no OpenAI credits."""
import json

import pytest

from app.services.conversation_context import ConversationContext
from app.services.conversation_prompt import ConversationPromptBuilder, PROMPT_VERSION, feedback_contract_example
from app.services.feedback_consistency import evaluate_feedback_consistency
from app.services.structured_feedback import CoachTurnOutput


ORIGINAL_FR = "Salut mon coach, ça va ? Comment vas-tu ?"
ORIGINAL_EN = "Hey manager, what's up?"


def context(**changes):
    data = dict(language_variant="fr-CA", language_name="French", current_cefr="B2",
                target_cefr="C1", training_mode="professional", communication_register="formal",
                scenario_key="meeting", recent_messages=())
    data.update(changes)
    return ConversationContext(**data)


def output(original, suggestion, improved):
    payload = json.loads(feedback_contract_example())
    payload["feedback"]["register"] = {
        "status": "improvement_possible", "explanation": "More suitable for a formal meeting.",
        "suggestion": suggestion,
    }
    payload["feedback"]["improved_version"] = improved
    return CoachTurnOutput.model_validate(payload)


def test_prompt_v3_preserves_json_contract():
    prompt = ConversationPromptBuilder().build(context())
    assert prompt.version == PROMPT_VERSION == "coach-v3"
    assert feedback_contract_example() in prompt.instructions
    assert "register.suggestion and improved_version" in prompt.instructions
    assert "grammatically correct informal" in prompt.instructions
    assert "Return only one valid JSON object" in prompt.instructions


@pytest.mark.parametrize("locale,language", [("fr-CA", "French"), ("en-CA", "English"), ("en-US", "English")])
def test_professional_prompt_explains_reformulation(locale, language):
    prompt = ConversationPromptBuilder().build(context(language_variant=locale, language_name=language))
    assert "professional register improvement" in prompt.instructions
    assert "do not repeat the unchanged learner utterance" in prompt.instructions
    assert locale in prompt.instructions


def test_fr_ca_unmodified_professional_sentence_is_flagged():
    finding = evaluate_feedback_consistency(
        learner_text=ORIGINAL_FR,
        output=output(ORIGINAL_FR, "Bonjour, comment allez-vous ?", ORIGINAL_FR),
        training_mode="professional", communication_register="formal")
    assert [f.code for f in finding] == ["professional_register_suggestion_not_reflected"]


def test_fr_ca_reformulation_resolves_flag():
    findings = evaluate_feedback_consistency(
        learner_text=ORIGINAL_FR,
        output=output(ORIGINAL_FR, "Bonjour, comment allez-vous ?", "Bonjour, comment allez-vous ?"),
        training_mode="professional", communication_register="formal")
    assert findings == ()


def test_en_professional_unmodified_sentence_is_flagged():
    findings = evaluate_feedback_consistency(
        learner_text=ORIGINAL_EN,
        output=output(ORIGINAL_EN, "Good morning. How are you?", ORIGINAL_EN),
        training_mode="professional", communication_register="professional")
    assert len(findings) == 1 and findings[0].dimension == "register"


def test_en_professional_reformulation_resolves_flag():
    findings = evaluate_feedback_consistency(
        learner_text=ORIGINAL_EN,
        output=output(ORIGINAL_EN, "Good morning. How are you?", "Good morning. How are you doing today?"),
        training_mode="professional", communication_register="professional")
    assert findings == ()


def test_general_informal_maintains_original_without_false_positive():
    findings = evaluate_feedback_consistency(
        learner_text=ORIGINAL_FR,
        output=output(ORIGINAL_FR, "Bonjour, comment allez-vous ?", ORIGINAL_FR),
        training_mode="conversation", communication_register="informal")
    assert findings == ()
    prompt = ConversationPromptBuilder().build(context(training_mode="conversation", communication_register="informal"))
    assert "Do not force formal expressions in informal/general practice" in prompt.instructions


def test_correct_register_no_suggestion_does_not_trigger():
    payload = json.loads(feedback_contract_example())
    payload["feedback"]["improved_version"] = ORIGINAL_FR
    result = CoachTurnOutput.model_validate(payload)
    assert evaluate_feedback_consistency(learner_text=ORIGINAL_FR, output=result,
        training_mode="professional", communication_register="formal") == ()


def test_normalization_ignores_spacing_and_case():
    result = output(ORIGINAL_EN, "Good morning. How are you?", "  HEY manager,  what's up? ")
    findings = evaluate_feedback_consistency(learner_text=ORIGINAL_EN, output=result,
        training_mode="professional", communication_register="formal")
    assert len(findings) == 1
