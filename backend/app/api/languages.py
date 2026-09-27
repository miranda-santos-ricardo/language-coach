from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Language, LanguageVariant
from app.schemas import LanguageRead, LanguageVariantRead
from app.schemas.common import LanguageCode
from app.services import (
    InactiveReferenceDataError,
    LanguageNotFoundError,
    LanguageService,
)

router = APIRouter(prefix="/languages", tags=["languages"])
service = LanguageService()


@router.get("", response_model=list[LanguageRead])
def list_languages(
    session: Annotated[Session, Depends(get_db)],
) -> list[Language]:
    return service.list(session)


@router.get(
    "/{language_code}/variants",
    response_model=list[LanguageVariantRead],
)
def list_language_variants(
    language_code: LanguageCode,
    session: Annotated[Session, Depends(get_db)],
) -> list[LanguageVariant]:
    try:
        return service.list_variants(session, language_code)
    except (LanguageNotFoundError, InactiveReferenceDataError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
