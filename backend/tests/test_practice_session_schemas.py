import pytest
from pydantic import ValidationError

from app.models.enums import CEFRLevel, TrainingMode
from app.schemas.practice_session import PracticeSessionCreate

def test_create_session_allows_default_cefr() -> None:
    payload = PracticeSessionCreate(
        training_mode="conversation",
        register="everyday",
    )

    assert payload.target_cefr is None


def test_create_free_talk_session_schema() -> None:
    payload = PracticeSessionCreate(
        training_mode="free_talk",
        register="conversational",
    )

    assert payload.training_mode == TrainingMode.FREE_TALK


def test_create_session_rejects_invalid_training_mode() -> None:
    with pytest.raises(ValidationError):
        PracticeSessionCreate(
            training_mode="something_invalid",
            register="everyday",
        )


def test_create_session_rejects_invalid_cefr() -> None:
    with pytest.raises(ValidationError):
        PracticeSessionCreate(
            training_mode="professional",
            register="professional",
            target_cefr="C9",
        )


def test_create_session_rejects_empty_register() -> None:
    with pytest.raises(ValidationError):
        PracticeSessionCreate(
            training_mode="professional",
            register="",
        )

def test_create_session_serializes_register_using_api_alias() -> None:
    payload = PracticeSessionCreate.model_validate(
        {
            "training_mode": "professional",
            "register": "formal_executive",
        }
    )

    serialized = payload.model_dump(by_alias=True)

    assert serialized["register"] == "formal_executive"
    assert "register_code" not in serialized

def test_create_professional_session_schema() -> None:
    payload = PracticeSessionCreate.model_validate(
        {
            "training_mode": "professional",
            "register": "formal_executive",
            "target_cefr": "C1",
        }
    )

    assert payload.training_mode == TrainingMode.PROFESSIONAL
    assert payload.register_code == "formal_executive"
    assert payload.target_cefr == CEFRLevel.C1
    assert payload.scenario_key is None