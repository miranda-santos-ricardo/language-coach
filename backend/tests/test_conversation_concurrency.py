"""Concurrency, replay and recovery checks. No real model calls."""
import threading
import uuid

import pytest
from sqlalchemy import select

from app.models import ConversationTurn, LanguageFeedback
from app.services.conversation_lock import ConversationBusyError, conversation_execution_gate
from app.services.conversation_service import ConversationService, ConversationRequestConflictError
from app.services.llm_errors import LLMTimeoutError
from app.services.structured_feedback import FeedbackValidationError
from tests.test_conversation_context_integration import create_case
from tests.test_conversation_service import FakeLLM, submit


def test_second_submission_is_rejected_before_provider(service_session):
    db = service_session
    user, profile, practice = create_case(db)
    llm = FakeLLM()
    with conversation_execution_gate(db, practice.id):
        with pytest.raises(ConversationBusyError):
            submit(ConversationService(llm=llm), db, user, profile, practice)
    assert llm.calls == []
    assert db.scalars(select(ConversationTurn)).all() == []


def test_different_practice_sessions_are_not_blocked(service_session):
    db = service_session
    user1, profile1, practice1 = create_case(db)
    user2, profile2, practice2 = create_case(db)
    with conversation_execution_gate(db, practice1.id):
        result = submit(ConversationService(llm=FakeLLM()), db, user2, profile2, practice2)
    assert result.turn_index == 1


def test_parallel_lock_attempt_from_thread_fails_fast(service_session):
    db = service_session
    _, _, practice = create_case(db)
    errors = []
    def competing():
        try:
            with conversation_execution_gate(db, practice.id):
                raise AssertionError("competing request entered gate")
        except ConversationBusyError as exc:
            errors.append(exc)
    with conversation_execution_gate(db, practice.id):
        thread = threading.Thread(target=competing)
        thread.start()
        thread.join(timeout=3)
        assert not thread.is_alive()
    assert len(errors) == 1


def test_retry_after_success_is_replayed_without_provider(service_session):
    db = service_session
    user, profile, practice = create_case(db)
    llm = FakeLLM()
    svc = ConversationService(llm=llm)
    request_id = uuid.uuid4()
    first = submit(svc, db, user, profile, practice, request_id=request_id)
    second = submit(svc, db, user, profile, practice, request_id=request_id)
    assert first.turn_id == second.turn_id and second.replayed
    assert len(llm.calls) == 1
    assert len(db.scalars(select(ConversationTurn)).all()) == 1


def test_reused_key_with_changed_text_still_conflicts(service_session):
    db = service_session
    user, profile, practice = create_case(db)
    llm = FakeLLM()
    svc = ConversationService(llm=llm)
    request_id = uuid.uuid4()
    submit(svc, db, user, profile, practice, request_id=request_id)
    with pytest.raises(ConversationRequestConflictError):
        submit(svc, db, user, profile, practice, request_id=request_id, text="Autre message")
    assert len(llm.calls) == 1
    assert len(db.scalars(select(ConversationTurn)).all()) == 1


@pytest.mark.parametrize("failure", ["timeout", "invalid_output"])
def test_failed_request_releases_gate_and_preserves_atomicity(service_session, failure):
    db = service_session
    user, profile, practice = create_case(db)
    request_id = uuid.uuid4()
    bad_llm = FakeLLM(exc=LLMTimeoutError("timeout")) if failure == "timeout" else FakeLLM(content='{"invalid":true}')
    exc = LLMTimeoutError if failure == "timeout" else FeedbackValidationError
    with pytest.raises(exc):
        submit(ConversationService(llm=bad_llm), db, user, profile, practice, request_id=request_id)
    assert db.scalars(select(ConversationTurn)).all() == []
    assert db.scalars(select(LanguageFeedback)).all() == []
    recovered = submit(ConversationService(llm=FakeLLM()), db, user, profile, practice, request_id=request_id)
    assert recovered.turn_index == 1 and not recovered.replayed


def test_database_error_rolls_back_and_allows_new_attempt(service_session, monkeypatch):
    db = service_session
    user, profile, practice = create_case(db)
    from app.repositories.conversation_turn import ConversationTurnRepository
    original = ConversationTurnRepository.add_with_feedback
    def fail_after_flush(session, turn, feedback):
        original(session, turn, feedback)
        raise RuntimeError("simulated failed write")
    with monkeypatch.context() as m:
        m.setattr(ConversationTurnRepository, "add_with_feedback", fail_after_flush)
        with pytest.raises(RuntimeError):
            submit(ConversationService(llm=FakeLLM()), db, user, profile, practice)
    assert db.scalars(select(ConversationTurn)).all() == []
    assert db.scalars(select(LanguageFeedback)).all() == []
    success = submit(ConversationService(llm=FakeLLM()), db, user, profile, practice)
    assert success.turn_index == 1

class _FakePGSession:
    def __init__(self, acquired):
        self.acquired = acquired
        self.queries = []
        self.rollbacks = 0
    def get_bind(self):
        class Engine:
            class dialect:
                name = "postgresql"
        return Engine()
    def scalar(self, statement, params):
        self.queries.append((str(statement), params))
        return self.acquired
    def rollback(self):
        self.rollbacks += 1


def test_postgres_gate_uses_transaction_advisory_lock():
    db = _FakePGSession(acquired=True)
    practice_id = uuid.uuid4()
    with conversation_execution_gate(db, practice_id):
        assert len(db.queries) == 1
    sql, params = db.queries[0]
    assert "pg_try_advisory_xact_lock" in sql
    assert -(2**63) <= params["key"] < 2**63
    assert db.rollbacks == 0  # service commits or rolls back transaction


def test_postgres_busy_releases_implicit_transaction():
    db = _FakePGSession(acquired=False)
    with pytest.raises(ConversationBusyError):
        with conversation_execution_gate(db, uuid.uuid4()):
            pytest.fail("gate must not admit competing request")
    assert db.rollbacks == 1
