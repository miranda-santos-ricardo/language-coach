from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CommunicationRegister


class CommunicationRegisterRepository:
    @staticmethod
    def get_by_code(
        session: Session,
        code: str,
    ) -> CommunicationRegister | None:
        statement = select(CommunicationRegister).where(
            CommunicationRegister.code == code
        )
        return session.scalar(statement)

    @staticmethod
    def get_by_codes(
        session: Session,
        codes: list[str],
    ) -> list[CommunicationRegister]:
        if not codes:
            return []

        statement = select(CommunicationRegister).where(
            CommunicationRegister.code.in_(codes)
        )
        return list(session.scalars(statement))

    @staticmethod
    def list_active(session: Session) -> list[CommunicationRegister]:
        statement = (
            select(CommunicationRegister)
            .where(CommunicationRegister.is_active.is_(True))
            .order_by(CommunicationRegister.code)
        )
        return list(session.scalars(statement))

    def get_by_code(
        self,
        code: str,
    ) -> CommunicationRegister | None:
        statement = select(CommunicationRegister).where(
            CommunicationRegister.code == code
        )

        return self.scalar(statement)