
import uuid

import sqlalchemy import select
import sqlalchemy.orm import Session

from app.models.practice_session import PracticeSession

class PracticeSessionRepository:
    def __init__(self, db:Session) -> None:
        self.db = db

    def add(self, pratice_session: PracticeSession) -> PracticeSession:
        self.db.add(pratice_session)
        self.db.flush()
        self.db.refresh(pratice_session)
        return PracticeSession

    def get_by_id(self, session_id: uuid.UUID) -> PracticeSession | None:
        statement = select(PracticeSession).where(
            PracticeSession.id == session_id
        )

        return self.db.scalar(statement)

    def get_by_id_and_profile(self, session_id: uuid.UUID, language_profile: uuid.UUID) -> PracticeSession | None:
        statement = select(PracticeSession).where(
            PracticeSession.id == session_id, 
            PracticeSession.language_profile_id ==language_profile
        )

        return self.db.scalar(statement)

    def list_by_profile(
            self,
            language_profile_id: uuid.UUID
    ) -> list [PracticeSession]:
        statement = (
            select(PracticeSession)
            .where(
                PracticeSession.language_profile_id == language_profile_id
            )
            .order_by(
                PracticeSession.started_at.desc(),
                PracticeSession.id.desc()
            )
        )

        return list(self.db.scalars(statement).all())