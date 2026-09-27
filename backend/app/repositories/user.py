import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    @staticmethod
    def add(session: Session, user: User) -> None:
        session.add(user)

    @staticmethod
    def get(session: Session, user_id: uuid.UUID) -> User | None:
        return session.get(User, user_id)

    @staticmethod
    def list(session: Session) -> list[User]:
        statement = select(User).order_by(User.display_name, User.id)
        return list(session.scalars(statement))
