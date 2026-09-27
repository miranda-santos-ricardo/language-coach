from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import CommunicationRegister
from app.repositories import CommunicationRegisterRepository


class CommunicationRegisterService:
    def __init__(
        self,
        repository: type[CommunicationRegisterRepository] = (
            CommunicationRegisterRepository
        ),
    ) -> None:
        self.repository = repository

    def list(self, session: Session) -> list[CommunicationRegister]:
        return self.repository.list_active(session)
