import uuid

from app.services.errors import (
    CommunicationRegisterNotFoundError, 
    InactiveReferenceDataError, 
    LanguageProfileNotFoundError,
    PracticeSessionNotFoundError, 
    RegisterModeNotAllowedError, 
    UserNotFoundError
)

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db

from app.schemas.practice_session import (
    PracticeSessionCreate,
    PracticeSessionRead,
)

from app.services.practice_session import PracticeSessionService
from app.services.practice_session_mapper import to_practice_session_read

router = APIRouter(
    prefix="/users/{user_id}/language-profiles/{profile_id}/sessions",
    tags=["practice-sessions"]
)

service = PracticeSessionService()

@router.post(
    "",
    response_model=PracticeSessionRead,
    status_code=status.HTTP_201_CREATED
)
def create_practice_session (
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    payload:PracticeSessionCreate,
    db: Session = Depends (get_db)
) -> PracticeSessionRead:
    try:
                
        practice_session = service.create(
            db,
            user_id,
            profile_id,
            payload
        )

        return to_practice_session_read(practice_session)

    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except LanguageProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except CommunicationRegisterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except (
        InactiveReferenceDataError,
        RegisterModeNotAllowedError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

@router.get(
    "",
    response_model=list[PracticeSessionRead]
)
def list_practice_session(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    db: Session = Depends (get_db)
) -> list[PracticeSessionRead]:

    try:
        sessions = service.list(
            db,
            user_id,
            profile_id,
        )

        return [
            to_practice_session_read(practice_session)
            for practice_session in sessions
        ]

    except (
        UserNotFoundError,
        LanguageProfileNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

@router.get(
    "/{practice_session_id}",
    response_model=PracticeSessionRead,
)
def get_practice_session(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    practice_session_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> PracticeSessionRead:
    try:
        practice_session = service.get(
            db,
            user_id,
            profile_id,
            practice_session_id,
        )

        return to_practice_session_read(practice_session)

    except (
        UserNotFoundError,
        LanguageProfileNotFoundError,
        PracticeSessionNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc