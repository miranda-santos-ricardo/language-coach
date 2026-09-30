import uuid

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.enums import SessionStatus
from app.models.practice_session import PracticeSession
from app.repositories.language_profile import LanguageProfileRepository
from app.repositories.practice_session import PracticeSessionRepository


class PracticeSessionNotFoundError(Exception):
    pass


class LanguageProfileNotFoundError(Exception):
    pass


class CommunicationRegisterNotFoundError(Exception):
    pass


class InvalidCommunicationRegisterError(Exception):
    pass


class PracticeSessionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.sessions = PracticeSessionRepository(db)

    def create(
        self,
        *,
        user_id: uuid.UUID,
        profile_id: uuid.UUID,
        payload: PracticeSessionCreate,
    ) -> PracticeSession:
        ...