"""Regression guard for shared fixtures used by multiple Phase 7 test modules."""
from uuid import uuid4
import pytest
from tests.support.assessment_models import Base, LanguageVariant, LanguageProfile, PracticeSession, ConversationTurn
from tests.support.sqlalchemy_resolver_fixtures import store, resolver, Turn
from app.services.conversation_turn_assessment import TurnAssessmentError

def test_shared_sql_models_are_distinct_from_production():
    assert set(Base.metadata.tables) == {
        "language_variants", "language_profiles", "practice_sessions", "conversation_turns"
    }

def test_shared_resolver_fixture_denies_cross_user(store):
    db, (owner, other, profile, session, turn) = store
    assert resolver(db)(owner, session, turn).user_id == owner
    with pytest.raises(TurnAssessmentError):
        resolver(db)(other, session, turn)

def test_shared_resolver_fixture_denies_unknown_turn(store):
    db, (owner, other, profile, session, turn) = store
    with pytest.raises(TurnAssessmentError):
        resolver(db)(owner, session, uuid4())
