from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    CommunicationRegister,
    PracticeSession,
    SessionStatus,
)
from app.repositories import (
    CommunicationRegisterRepository,
    LanguageProfileRepository,
    PracticeSessionRepository,
    UserRepository,
)
from app.schemas import PracticeSessionCreate
from app.services.errors import (
    CommunicationRegisterNotFoundError,
    InactiveReferenceDataError,
    LanguageProfileNotFoundError,
    PracticeSessionNotFoundError,
    RegisterModeNotAllowedError,
    UserNotFoundError,
    InvalidPracticeSessionTransitionError
)


class PracticeSessionService:
    def __init__(
        self,
        user_repository: type[UserRepository] = UserRepository,
        register_repository: type[CommunicationRegisterRepository] = (
            CommunicationRegisterRepository
        ),
        profile_repository: type[LanguageProfileRepository] = (
            LanguageProfileRepository
        ),
        practice_session_repository: type[PracticeSessionRepository] = (
            PracticeSessionRepository
        ),
    ) -> None:
        self.user_repository = user_repository
        self.register_repository = register_repository
        self.profile_repository = profile_repository
        self.practice_session_repository = practice_session_repository

    def create(
        self,
        session: Session,
        user_id: uuid.UUID,
        profile_id: uuid.UUID,
        data: PracticeSessionCreate,
    ) -> PracticeSession:
        self._require_user(session, user_id)

        profile = self._require_profile(
            session,
            user_id,
            profile_id,
        )

        register = self._resolve_register(
            session,
            data.register_code,
        )

        now = datetime.now(timezone.utc)

        practice_session = PracticeSession(
            language_profile_id=profile.id,
            training_mode=data.training_mode,
            communication_register_id=register.id,
            profile_cefr_snapshot=profile.cefr_level,
            target_cefr=data.target_cefr,
            scenario_key=data.scenario_key,
            status=SessionStatus.ACTIVE,
            started_at=now,
            ended_at=None,
        )

        practice_session.language_profile = profile
        practice_session.communication_register = register

        self.practice_session_repository.add(
            session,
            practice_session,
        )

        self._commit_session_write(session)

        created = self.practice_session_repository.get_owned(
            session,
            profile.id,
            practice_session.id,
        )

        assert created is not None
        return created

    def get(
        self,
        session: Session,
        user_id: uuid.UUID,
        profile_id: uuid.UUID,
        practice_session_id: uuid.UUID,
    ) -> PracticeSession:
        self._require_user(session, user_id)

        profile = self._require_profile(
            session,
            user_id,
            profile_id,
        )

        practice_session = self.practice_session_repository.get_owned(
            session,
            profile.id,
            practice_session_id,
        )

        if practice_session is None:
            raise PracticeSessionNotFoundError(
                f"practice session {practice_session_id} was not found "
                f"for language profile {profile_id}"
            )

        return practice_session

    def list(
        self,
        session: Session,
        user_id: uuid.UUID,
        profile_id: uuid.UUID,
    ) -> list[PracticeSession]:
        self._require_user(session, user_id)

        profile = self._require_profile(
            session,
            user_id,
            profile_id,
        )

        return self.practice_session_repository.list_for_profile(
            session,
            profile.id,
        )

    def _require_user(
        self,
        session: Session,
        user_id: uuid.UUID,
    ) -> None:
        if self.user_repository.get(session, user_id) is None:
            raise UserNotFoundError(
                f"user {user_id} was not found"
            )

    def _require_profile(
        self,
        session: Session,
        user_id: uuid.UUID,
        profile_id: uuid.UUID,
    ):
        profile = self.profile_repository.get_owned(
            session,
            user_id,
            profile_id,
        )

        if profile is None:
            raise LanguageProfileNotFoundError(
                f"language profile {profile_id} was not found "
                f"for user {user_id}"
            )

        return profile

    def _resolve_register(
        self,
        session: Session,
        code: str,
    ) -> CommunicationRegister:
        register = self.register_repository.get_by_code(
            session,
            code,
        )

        if register is None:
            raise CommunicationRegisterNotFoundError(
                f"communication register {code!r} was not found"
            )

        if not register.is_active:
            raise InactiveReferenceDataError(
                f"communication register {code!r} is inactive"
            )

        if not register.production_allowed:
            raise RegisterModeNotAllowedError(
                f"communication register {code!r} "
                "does not allow production"
            )

        return register

    @staticmethod
    def _commit_session_write(
        session: Session,
    ) -> None:
        session.commit()

    def complete(
            self,
            session:Session,
            user_id: uuid.UUID,
            profile_id:uuid.UUID,
            practice_session_id:uuid.UUID
    ) -> PracticeSession:

        practice_session = self.get(
            session, 
            user_id,
            profile_id,
            practice_session_id
        )

        self._require_active(practice_session)

        practice_session.status = SessionStatus.COMPLETED
        practice_session.ended_at = datetime.now(timezone.utc)

        self._commit_session_write(session)

        return practice_session


    def abandon(
        self,
        session: Session,
        user_id: uuid.UUID,
        profile_id: uuid.UUID,
        practice_session_id: uuid.UUID,
    ) -> PracticeSession:
        practice_session = self.get(
            session,
            user_id,
            profile_id,
            practice_session_id,
        )

        self._require_active(practice_session)

        practice_session.status = SessionStatus.ABANDONED
        practice_session.ended_at = datetime.now(timezone.utc)

        self._commit_session_write(session)

        return practice_session

    @staticmethod
    def _require_active(
        practice_session: PracticeSession,
    ) -> None:
        if practice_session.status != SessionStatus.ACTIVE:
            raise InvalidPracticeSessionTransitionError(
                "Only an active practice session can transition "
                "to a terminal status"
            )