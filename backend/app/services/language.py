from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Language, LanguageVariant
from app.repositories import LanguageRepository
from app.services.errors import InactiveReferenceDataError, LanguageNotFoundError


class LanguageService:
    def __init__(
        self,
        repository: type[LanguageRepository] = LanguageRepository,
    ) -> None:
        self.repository = repository

    def list(self, session: Session) -> list[Language]:
        return self.repository.list_active(session)

    def list_variants(
        self,
        session: Session,
        language_code: str,
    ) -> list[LanguageVariant]:
        language = self.repository.get_by_code(session, language_code)
        if language is None:
            raise LanguageNotFoundError(
                f"language {language_code!r} was not found"
            )
        if not language.is_active:
            raise InactiveReferenceDataError(
                f"language {language_code!r} is inactive"
            )
        return self.repository.list_active_variants(session, language.id)
