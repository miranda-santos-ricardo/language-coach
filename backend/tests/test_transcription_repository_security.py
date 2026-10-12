"""Step 9.2.2: SQL-backed ownership checks (no external STT calls)."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CEFRLevel,
    CommunicationRegister,
    LanguageProfile,
    LanguageVariant,
    PracticeSession,
    SessionStatus,
    TrainingMode,
    User,
)
from app.repositories import LanguageProfileRepository, PracticeSessionRepository
from app.services.errors import (
    LanguageProfileNotFoundError,
    PracticeSessionNotFoundError,
)
from app.services.practice_session import PracticeSessionService


@pytest.fixture
def ownership_data(service_session: Session):
    """Persist two users, one profile and one active session per user."""
    variant = service_session.scalar(
        select(LanguageVariant).where(LanguageVariant.code == "fr-CA")
    )
    register = service_session.scalar(
        select(CommunicationRegister).where(
            CommunicationRegister.code == "professional"
        ))
    assert variant is not None
    assert register is not None

    user_a = User(display_name="Ownership Test A")
    user_b = User(display_name="Ownership Test B")
    service_session.add_all([user_a, user_b])
    service_session.flush()

    cefr = next(iter(CEFRLevel))
    mode = next(iter(TrainingMode))
    profile_a = LanguageProfile(
        user_id=user_a.id,
        language_variant_id=variant.id,
        cefr_level=cefr,
        default_production_register_id=register.id,
    )
    profile_b = LanguageProfile(
        user_id=user_b.id,
        language_variant_id=variant.id,
        cefr_level=cefr,
        default_production_register_id=register.id,
    )
    service_session.add_all([profile_a, profile_b])
    service_session.flush()

    now = datetime.now(timezone.utc)
    session_a = PracticeSession(
        language_profile_id=profile_a.id,
        training_mode=mode,
        communication_register_id=register.id,
        profile_cefr_snapshot=cefr,
        status=SessionStatus.ACTIVE,
        started_at=now,
        ended_at=None,
    )
    session_b = PracticeSession(
        language_profile_id=profile_b.id,
        training_mode=mode,
        communication_register_id=register.id,
        profile_cefr_snapshot=cefr,
        status=SessionStatus.ACTIVE,
        started_at=now,
        ended_at=None,
    )
    service_session.add_all([session_a, session_b])
    service_session.commit()

    return SimpleNamespace(
        db=service_session,
        user_a=user_a,
        user_b=user_b,
        profile_a=profile_a,
        profile_b=profile_b,
        session_a=session_a,
        session_b=session_b,
    )


def test_owner_can_retrieve_own_profile(ownership_data):
    data = ownership_data
    found = LanguageProfileRepository.get_owned(
        data.db, data.user_a.id, data.profile_a.id
    )
    assert found is not None
    assert found.id == data.profile_a.id


def test_other_user_cannot_retrieve_profile(ownership_data):
    data = ownership_data
    assert LanguageProfileRepository.get_owned(
        data.db, data.user_b.id, data.profile_a.id
    ) is None
    with pytest.raises(LanguageProfileNotFoundError):
        PracticeSessionService().get(
            data.db, data.user_b.id, data.profile_a.id, data.session_a.id
        )


def test_owner_can_retrieve_own_session(ownership_data):
    data = ownership_data
    found = PracticeSessionService().get(
        data.db, data.user_a.id, data.profile_a.id, data.session_a.id
    )
    assert found.id == data.session_a.id
    assert found.status == SessionStatus.ACTIVE


def test_other_profile_cannot_retrieve_session(ownership_data):
    data = ownership_data
    assert PracticeSessionRepository.get_owned(
        data.db, data.profile_b.id, data.session_a.id
    ) is None
    with pytest.raises(PracticeSessionNotFoundError):
        PracticeSessionService().get(
            data.db, data.user_b.id, data.profile_b.id, data.session_a.id
        )


def test_nonexistent_session_is_not_returned(ownership_data):
    data = ownership_data
    unknown_id = uuid4()
    assert PracticeSessionRepository.get_owned(
        data.db, data.profile_a.id, unknown_id
    ) is None
    with pytest.raises(PracticeSessionNotFoundError):
        PracticeSessionService().get(
            data.db, data.user_a.id, data.profile_a.id, unknown_id
        )


def test_profile_and_session_lists_are_scoped_to_owner(ownership_data):
    data = ownership_data
    profiles = LanguageProfileRepository.list_for_user(data.db, data.user_a.id)
    sessions = PracticeSessionRepository.list_for_profile(
        data.db, data.profile_a.id
    )
    assert [profile.id for profile in profiles] == [data.profile_a.id]
    assert [practice_session.id for practice_session in sessions] == [
        data.session_a.id
    ]
    assert data.profile_b.id not in [profile.id for profile in profiles]
    assert data.session_b.id not in [item.id for item in sessions]
