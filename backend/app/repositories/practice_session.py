import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PracticeSession


class PracticeSessionRepository:
    @staticmethod
    def add(
        session: Session,
        practice_session: PracticeSession,
    ) -> None:
        session.add(practice_session)

    @staticmethod
    def get_owned(
        session: Session,
        profile_id: uuid.UUID,
        practice_session_id: uuid.UUID,
    ) -> PracticeSession | None:
        statement = select(PracticeSession).where(
            PracticeSession.id == practice_session_id,
            PracticeSession.language_profile_id == profile_id,
        )

        return session.scalar(statement)

    @staticmethod
    def list_for_profile(
        session: Session,
        profile_id: uuid.UUID,
    ) -> list[PracticeSession]:
        statement = (
            select(PracticeSession)
            .where(
                PracticeSession.language_profile_id == profile_id
            )
            .order_by(
                PracticeSession.started_at.desc(),
                PracticeSession.id.desc(),
            )
        )

        return list(session.scalars(statement))