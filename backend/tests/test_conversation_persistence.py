import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (CEFRLevel, CommunicationRegister, ConversationTurn,
                        LanguageFeedback, LanguageProfile, LanguageVariant,
                        PracticeSession, SessionStatus, TrainingMode, User)
from app.repositories.conversation_turn import ConversationTurnRepository as Repo


def make_session(db):
    user = User(display_name="Learner")
    db.add(user)
    db.flush()
    variant = db.query(LanguageVariant).filter_by(code="fr-CA").one()
    register = db.query(CommunicationRegister).filter_by(code="professional").one()
    profile = LanguageProfile(user_id=user.id, language_variant_id=variant.id,
                              cefr_level=CEFRLevel.B2, default_production_register_id=register.id)
    db.add(profile)
    db.flush()
    session = PracticeSession(language_profile_id=profile.id,
                              training_mode=TrainingMode.PROFESSIONAL,
                              communication_register_id=register.id,
                              profile_cefr_snapshot=CEFRLevel.B2,
                              status=SessionStatus.ACTIVE,
                              started_at=datetime.now(timezone.utc))
    db.add(session)
    db.flush()
    return user.id, profile.id, session.id


def make_turn(sid, index=1, request_id=None):
    turn = ConversationTurn(practice_session_id=sid, turn_index=index,
                            client_request_id=request_id or uuid.uuid4(),
                            input_modality="text", learner_text="Bonjour",
                            coach_response="Bonjour, comment allez-vous?")
    feedback = LanguageFeedback(overall_assessment="Good", grammar_feedback={"status":"correct"},
                                vocabulary_feedback={}, clarity_feedback={}, naturalness_feedback={},
                                register_feedback={}, improved_version="Bonjour", explanations=[],
                                strengths=["Clear"], next_recommendation="Continue")
    return turn, feedback


def test_atomic_insert_and_scoped_reads(service_session):
    db = service_session
    user, profile, sid = make_session(db)
    turn, feedback = make_turn(sid)
    Repo.add_with_feedback(db, turn, feedback)
    db.commit()
    saved = Repo.get_owned(db, user, profile, sid, turn.id)
    assert saved is not None and saved.feedback.id == feedback.id
    assert Repo.get_by_request_id(db, user, profile, sid, turn.client_request_id).id == turn.id
    assert Repo.list_owned(db, user, profile, sid)[0].id == turn.id
    assert Repo.get_owned(db, uuid.uuid4(), profile, sid, turn.id) is None
    assert Repo.get_owned(db, user, uuid.uuid4(), sid, turn.id) is None
    assert Repo.get_owned(db, user, profile, uuid.uuid4(), turn.id) is None


def test_turn_order_and_duplicate_constraints(service_session):
    db = service_session
    user, profile, sid = make_session(db)
    first, fb = make_turn(sid, 2)
    Repo.add_with_feedback(db, first, fb)
    second, fb2 = make_turn(sid, 1)
    Repo.add_with_feedback(db, second, fb2)
    db.commit()
    assert [t.turn_index for t in Repo.list_owned(db, user, profile, sid)] == [1, 2]
    duplicate, fbd = make_turn(sid, 1)
    with pytest.raises(IntegrityError):
        Repo.add_with_feedback(db, duplicate, fbd)
    db.rollback()
    assert len(Repo.list_owned(db, user, profile, sid)) == 2
    same_request, fbr = make_turn(sid, 3, request_id=first.client_request_id)
    with pytest.raises(IntegrityError):
        Repo.add_with_feedback(db, same_request, fbr)
    db.rollback()


def test_failed_feedback_rolls_back_turn(service_session):
    db = service_session
    user, profile, sid = make_session(db)
    db.commit()
    turn, feedback = make_turn(sid)
    feedback.overall_assessment = None
    with pytest.raises(IntegrityError):
        Repo.add_with_feedback(db, turn, feedback)
    db.rollback()
    assert Repo.list_owned(db, user, profile, sid) == []


def test_pagination_validation(service_session):
    db = service_session
    user, profile, sid = make_session(db)
    with pytest.raises(ValueError):
        Repo.list_owned(db, user, profile, sid, limit=101)
    with pytest.raises(ValueError):
        Repo.list_owned(db, user, profile, sid, offset=-1)


def test_flush_is_not_commit_and_rollback_removes_both_records(service_session):
    """The orchestration layer owns the transaction, even after flush succeeds."""
    db = service_session
    user, profile, sid = make_session(db)
    db.commit()
    turn, feedback = make_turn(sid)
    Repo.add_with_feedback(db, turn, feedback)
    assert Repo.get_owned(db, user, profile, sid, turn.id) is not None
    db.rollback()
    assert Repo.get_owned(db, user, profile, sid, turn.id) is None
    assert db.get(LanguageFeedback, feedback.id) is None


def test_failed_second_insert_rollback_preserves_previously_committed_turn(service_session):
    db = service_session
    user, profile, sid = make_session(db)
    first, first_feedback = make_turn(sid)
    Repo.add_with_feedback(db, first, first_feedback)
    db.commit()
    second, second_feedback = make_turn(sid, index=2)
    second_feedback.overall_assessment = None
    with pytest.raises(IntegrityError):
        Repo.add_with_feedback(db, second, second_feedback)
    db.rollback()
    assert [turn.id for turn in Repo.list_owned(db, user, profile, sid)] == [first.id]
    assert Repo.get_owned(db, user, profile, sid, first.id).feedback.id == first_feedback.id


def test_request_id_uniqueness_is_scoped_to_practice_session(service_session):
    db = service_session
    user, profile, first_sid = make_session(db)
    first, first_feedback = make_turn(first_sid)
    Repo.add_with_feedback(db, first, first_feedback)
    register = db.query(CommunicationRegister).filter_by(code="professional").one()
    second_session = PracticeSession(language_profile_id=profile, training_mode=TrainingMode.PROFESSIONAL,
                                     communication_register_id=register.id,
                                     profile_cefr_snapshot=CEFRLevel.B2, status=SessionStatus.ACTIVE,
                                     started_at=datetime.now(timezone.utc))
    db.add(second_session)
    db.flush()
    second, second_feedback = make_turn(second_session.id, request_id=first.client_request_id)
    Repo.add_with_feedback(db, second, second_feedback)
    db.commit()
    assert Repo.get_by_request_id(db, user, profile, first_sid, first.client_request_id).id == first.id
    assert Repo.get_by_request_id(db, user, profile, second_session.id, first.client_request_id).id == second.id


@pytest.mark.parametrize("field,value", [
    ("turn_index", 0), ("turn_index", -1), ("input_modality", "audio"),
    ("learner_text", "   "), ("coach_response", "   "),
])
def test_turn_database_check_constraints(service_session, field, value):
    db = service_session
    _, _, sid = make_session(db)
    db.commit()
    turn, feedback = make_turn(sid)
    setattr(turn, field, value)
    with pytest.raises(IntegrityError):
        Repo.add_with_feedback(db, turn, feedback)
    db.rollback()
    assert db.query(ConversationTurn).count() == 0
    assert db.query(LanguageFeedback).count() == 0


def test_foreign_key_rejects_orphan_turn_and_feedback(service_session):
    db = service_session
    orphan, feedback = make_turn(uuid.uuid4())
    with pytest.raises(IntegrityError):
        Repo.add_with_feedback(db, orphan, feedback)
    db.rollback()
    feedback = make_turn(uuid.uuid4())[1]
    feedback.conversation_turn_id = uuid.uuid4()
    db.add(feedback)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_repository_rejects_invalid_page_limit_and_offset(service_session):
    db = service_session
    user, profile, sid = make_session(db)
    for limit, offset in [(0, 0), (-1, 0), (101, 0), (50, -1)]:
        with pytest.raises(ValueError, match="Invalid pagination"):
            Repo.list_owned(db, user, profile, sid, limit=limit, offset=offset)
