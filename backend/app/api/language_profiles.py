import uuid
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import LanguageProfile
from app.schemas import (
    LanguageProfileCreate,
    LanguageProfileRead,
    LanguageProfileUpdate,
)
from app.services import (
    CommunicationRegisterNotFoundError,
    DuplicateLanguageProfileError,
    InactiveReferenceDataError,
    LanguageNotFoundError,
    LanguageProfileNotFoundError,
    LanguageProfileService,
    LanguageVariantMismatchError,
    LanguageVariantNotFoundError,
    RegisterModeNotAllowedError,
    ServiceError,
    UserNotFoundError,
)

router = APIRouter(
    prefix="/users/{user_id}/language-profiles",
    tags=["language-profiles"],
)
service = LanguageProfileService()

_NOT_FOUND_ERRORS = (
    UserNotFoundError,
    LanguageProfileNotFoundError,
)

_UNPROCESSABLE_ERRORS = (
    LanguageNotFoundError,
    LanguageVariantNotFoundError,
    LanguageVariantMismatchError,
    CommunicationRegisterNotFoundError,
    InactiveReferenceDataError,
    RegisterModeNotAllowedError,
)


def _raise_http_error(exc: ServiceError) -> NoReturn:
    if isinstance(exc, _NOT_FOUND_ERRORS):
        http_status = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, DuplicateLanguageProfileError):
        http_status = status.HTTP_409_CONFLICT
    elif isinstance(exc, _UNPROCESSABLE_ERRORS):
        http_status = status.HTTP_422_UNPROCESSABLE_CONTENT
    else:
        raise exc

    raise HTTPException(
        status_code=http_status,
        detail=str(exc),
    ) from exc


@router.post(
    "",
    response_model=LanguageProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_language_profile(
    user_id: uuid.UUID,
    data: LanguageProfileCreate,
    session: Annotated[Session, Depends(get_db)],
) -> LanguageProfile:
    try:
        return service.create(session, user_id, data)
    except ServiceError as exc:
        _raise_http_error(exc)


@router.get("", response_model=list[LanguageProfileRead])
def list_language_profiles(
    user_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db)],
) -> list[LanguageProfile]:
    try:
        return service.list(session, user_id)
    except ServiceError as exc:
        _raise_http_error(exc)


@router.get(
    "/{profile_id}",
    response_model=LanguageProfileRead,
)
def get_language_profile(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    session: Annotated[Session, Depends(get_db)],
) -> LanguageProfile:
    try:
        return service.get(session, user_id, profile_id)
    except ServiceError as exc:
        _raise_http_error(exc)


@router.patch(
    "/{profile_id}",
    response_model=LanguageProfileRead,
)
def update_language_profile(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    data: LanguageProfileUpdate,
    session: Annotated[Session, Depends(get_db)],
) -> LanguageProfile:
    try:
        return service.update(session, user_id, profile_id, data)
    except ServiceError as exc:
        _raise_http_error(exc)
