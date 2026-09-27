from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import User
from app.repositories import UserRepository
from app.schemas import UserCreate
from app.services.errors import UserNotFoundError


class UserService:
    def __init__(self, repository: type[UserRepository] = UserRepository) -> None:
        self.repository = repository

    def create(self, session: Session, data: UserCreate) -> User:
        user = User(display_name=data.display_name)
        self.repository.add(session, user)
        session.commit()
        session.refresh(user)
        return user

    def get(self, session: Session, user_id: uuid.UUID) -> User:
        user = self.repository.get(session, user_id)
        if user is None:
            raise UserNotFoundError(f"user {user_id} was not found")
        return user

    def list(self, session: Session) -> list[User]:
        return self.repository.list(session)
