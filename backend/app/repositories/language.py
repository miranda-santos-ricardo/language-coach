from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Language, LanguageVariant


class LanguageRepository:
    @staticmethod
    def get_by_code(session: Session, code: str) -> Language | None:
        statement = select(Language).where(Language.code == code)
        return session.scalar(statement)

    @staticmethod
    def list_active(session: Session) -> list[Language]:
        statement = (
            select(Language)
            .where(Language.is_active.is_(True))
            .order_by(Language.code)
        )
        return list(session.scalars(statement))

    @staticmethod
    def get_variant_by_code(
        session: Session,
        code: str,
    ) -> LanguageVariant | None:
        statement = (
            select(LanguageVariant)
            .options(joinedload(LanguageVariant.language))
            .where(LanguageVariant.code == code)
        )
        return session.scalar(statement)

    @staticmethod
    def list_active_variants(
        session: Session,
        language_id: int,
    ) -> list[LanguageVariant]:
        statement = (
            select(LanguageVariant)
            .where(
                LanguageVariant.language_id == language_id,
                LanguageVariant.is_active.is_(True),
            )
            .order_by(LanguageVariant.code)
        )
        return list(session.scalars(statement))
