import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.schemas import UserCreate, UserRead
from app.services import UserNotFoundError, UserService

router = APIRouter(prefix="/users", tags=["users"])
service = UserService()


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    data: UserCreate,
    session: Annotated[Session, Depends(get_db)],
) -> User:
    return service.create(session, data)


@router.get("", response_model=list[UserRead])
def list_users(
    session: Annotated[Session, Depends(get_db)],
) -> list[User]:
    return service.list(session)


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        return service.get(session, user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
