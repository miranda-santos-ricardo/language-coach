"""Mocked LLM + real SQLAlchemy repository and constraints."""
import json
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import ConversationTurn, LanguageFeedback
from app.services.conversation_service import (
    ConversationRequestConflictError, ConversationService, InvalidLearnerUtteranceError,
)
from app.services.conversation_context import ConversationContextNotFoundError, ConversationSessionInactiveError
from app.services.structured_feedback import FeedbackValidationError
from app.services.llm import LLMResult
from app.services.llm_errors import LLMTimeoutError
from tests.test_conversation_context_integration import create_case


def valid_response():
    dimension = {"status": "correct", "explanation": "No error found", "suggestion": None}
    return json.dumps({"coach_response": "Pouvez-vous développer?", "feedback": {
        "overall_assessment": "Good", "grammar": dimension, "vocabulary": dimension,
        "clarity": dimension, "naturalness": dimension, "register": dimension,
        "improved_version": "Bonjour", "explanations": [], "strengths": ["Clear"],
        "next_recommendation": "Continue"}})


class FakeLLM:
    def __init__(self, content=None, exc=None):
        self.content = content if content is not None else valid_response()
        self.exc = exc
        self.calls = []

    def generate(self, *, instructions, messages):
        self.calls.append((instructions, messages))
        if self.exc:
            raise self.exc
        return LLMResult(content=self.content, model="fake-model")


def submit(svc, db, user, profile, practice, **kwargs):
    return svc.submit(session=db, user_id=user.id, profile_id=profile.id,
                      practice_session_id=practice.id, text=kwargs.get("text", "Bonjour"),
                      input_modality=kwargs.get("modality", "text"),
                      client_request_id=kwargs.get("request_id", uuid.uuid4()))


def test_successful_orchestration_persists_atomic_turn_and_feedback(service_session):
    db = service_session
    user, profile, practice = create_case(db)
    llm = FakeLLM()
    outcome = submit(ConversationService(llm=llm), db, user, profile, practice)
    assert outcome.turn_index == 1 and outcome.model == "fake-model"
    assert outcome.prompt_version == "coach-v2" and not outcome.replayed
    assert len(llm.calls) == 1
    instructions, messages = llm.calls[0]
    assert "fr-CA" in instructions and "Bonjour" == messages[-1].content
    turn = db.scalar(select(ConversationTurn))
    assert turn.feedback is not None and turn.id == outcome.turn_id
    assert db.scalar(select(LanguageFeedback)).improved_version == "Bonjour"


def test_followup_includes_previous_exchange_and_increments_index(service_session):
    db = service_session
    user, profile, practice = create_case(db)
    llm = FakeLLM()
    service = ConversationService(llm=llm)
    submit(service, db, user, profile, practice)
    result = submit(service, db, user, profile, practice, text="Et ensuite?", modality="voice")
    assert result.turn_index == 2
    assert [(m.role, m.content) for m in llm.calls[1][1]] == [
        ("user", "Bonjour"), ("assistant", "Pouvez-vous développer?"),
        ("user", "Et ensuite?")]
    assert db.scalars(select(ConversationTurn).order_by(ConversationTurn.turn_index)).all()[1].input_modality == "voice"


def test_sequential_replay_has_no_second_llm_call(service_session):
    db = service_session
    user, profile, practice = create_case(db)
    llm = FakeLLM()
    service = ConversationService(llm=llm)
    request_id = uuid.uuid4()
    first = submit(service, db, user, profile, practice, request_id=request_id)
    second = submit(service, db, user, profile, practice, request_id=request_id)
    assert second.replayed and second.turn_id == first.turn_id
    assert second.feedback == first.feedback and len(llm.calls) == 1
    with pytest.raises(ConversationRequestConflictError):
        submit(service, db, user, profile, practice, request_id=request_id, text="Different")


@pytest.mark.parametrize("bad", ["", "  \t ", "x" * 4001, None])
def test_bad_input_rejected_before_provider(service_session, bad):
    db = service_session
    user, profile, practice = create_case(db)
    llm = FakeLLM()
    with pytest.raises(InvalidLearnerUtteranceError):
        submit(ConversationService(llm=llm), db, user, profile, practice, text=bad)
    assert not llm.calls


def test_invalid_modality_and_request_id(service_session):
    db = service_session
    user, profile, practice = create_case(db)
    llm = FakeLLM()
    with pytest.raises(InvalidLearnerUtteranceError):
        submit(ConversationService(llm=llm), db, user, profile, practice, modality="audio")
    with pytest.raises(InvalidLearnerUtteranceError):
        submit(ConversationService(llm=llm), db, user, profile, practice, request_id="not-uuid")
    assert not llm.calls


def test_owned_session_required_before_llm(service_session):
    db = service_session
    user, profile, practice = create_case(db)
    llm = FakeLLM()
    with pytest.raises(ConversationContextNotFoundError):
        ConversationService(llm=llm).submit(session=db, user_id=uuid.uuid4(), profile_id=profile.id,
            practice_session_id=practice.id, text="Bonjour", input_modality="text", client_request_id=uuid.uuid4())
    assert not llm.calls


def test_timeout_does_not_write_completed_turn(service_session):
    db = service_session
    user, profile, practice = create_case(db)
    with pytest.raises(LLMTimeoutError):
        submit(ConversationService(llm=FakeLLM(exc=LLMTimeoutError("Timeout"))), db, user, profile, practice)
    assert db.scalars(select(ConversationTurn)).all() == []


def test_invalid_feedback_does_not_write_completed_turn(service_session):
    db = service_session
    user, profile, practice = create_case(db)
    with pytest.raises(FeedbackValidationError):
        submit(ConversationService(llm=FakeLLM(content='{"bad":"output"}')), db, user, profile, practice)
    assert db.scalars(select(ConversationTurn)).all() == []


def test_persistence_failure_rolls_back_both_records(service_session, monkeypatch):
    db = service_session
    user, profile, practice = create_case(db)
    from app.repositories.conversation_turn import ConversationTurnRepository

    def fail_after_flush(session, turn, feedback):
        ConversationTurnRepository_original(session, turn, feedback)
        raise RuntimeError("simulated persistence failure")

    ConversationTurnRepository_original = ConversationTurnRepository.add_with_feedback
    monkeypatch.setattr(ConversationTurnRepository, "add_with_feedback", fail_after_flush)
    with pytest.raises(RuntimeError):
        submit(ConversationService(llm=FakeLLM()), db, user, profile, practice)
    assert db.scalars(select(ConversationTurn)).all() == []
    assert db.scalars(select(LanguageFeedback)).all() == []


def test_inactive_session_blocks_provider_call(service_session):
    from datetime import datetime, timezone
    from app.models import SessionStatus
    db = service_session
    user, profile, practice = create_case(db)
    practice.status = SessionStatus.COMPLETED
    practice.ended_at = datetime.now(timezone.utc)
    db.commit()
    llm = FakeLLM()
    with pytest.raises(ConversationSessionInactiveError):
        submit(ConversationService(llm=llm), db, user, profile, practice)
    assert llm.calls == []
