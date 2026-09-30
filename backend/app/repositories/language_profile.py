import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import LanguageProfile, LanguageVariant


class LanguageProfileRepository:
    _load_options = (
        joinedload(LanguageProfile.language_variant).joinedload(
            LanguageVariant.language
        ),
        joinedload(LanguageProfile.default_production_register),
        selectinload(LanguageProfile.comprehension_registers),
    )

    @classmethod
    def add(cls, session: Session, profile: LanguageProfile) -> None:
        session.add(profile)

    @classmethod
    def get_owned(
        cls,
        session: Session,
        user_id: uuid.UUID,
        profile_id: uuid.UUID,
    ) -> LanguageProfile | None:
        statement = (
            select(LanguageProfile)
            .options(*cls._load_options)
            .where(
                LanguageProfile.id == profile_id,
                LanguageProfile.user_id == user_id,
            )
        )
        return session.scalar(statement)

    @classmethod
    def list_for_user(
        cls,
        session: Session,
        user_id: uuid.UUID,
    ) -> list[LanguageProfile]:
        statement = (
            select(LanguageProfile)
            .options(*cls._load_options)
            .where(LanguageProfile.user_id == user_id)
            .order_by(LanguageProfile.created_at, LanguageProfile.id)
        )
        return list(session.scalars(statement))

    @staticmethod
    def exists_for_user_and_variant(
        session: Session,
        user_id: uuid.UUID,
        language_variant_id: int,
        *,
        exclude_profile_id: uuid.UUID | None = None,
    ) -> bool:
        statement = select(LanguageProfile.id).where(
            LanguageProfile.user_id == user_id,
            LanguageProfile.language_variant_id == language_variant_id,
        )

        if exclude_profile_id is not None:
            statement = statement.where(
                LanguageProfile.id != exclude_profile_id
            )

        return session.scalar(statement.limit(1)) is not None

    def get_by_id_and_user(
    self,
    profile_id: uuid.UUID,
    user_id: uuid.UUID,
    ) -> LanguageProfile | None:
        statement = select(LanguageProfile).where(
            LanguageProfile.id == profile_id,
            LanguageProfile.user_id == user_id,
        )

        return self.db.scalar(statement)
