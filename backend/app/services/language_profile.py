from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CommunicationRegister, LanguageProfile, LanguageVariant
from app.repositories import (
    CommunicationRegisterRepository,
    LanguageProfileRepository,
    LanguageRepository,
    UserRepository,
)
from app.schemas import LanguageProfileCreate, LanguageProfileUpdate
from app.services.errors import (
    CommunicationRegisterNotFoundError,
    DuplicateLanguageProfileError,
    InactiveReferenceDataError,
    LanguageNotFoundError,
    LanguageProfileNotFoundError,
    LanguageVariantMismatchError,
    LanguageVariantNotFoundError,
    RegisterModeNotAllowedError,
    UserNotFoundError,
)

_DUPLICATE_PROFILE_CONSTRAINT = "uq_language_profiles_user_language_variant"


class LanguageProfileService:
    def __init__(
        self,
        user_repository: type[UserRepository] = UserRepository,
        language_repository: type[LanguageRepository] = LanguageRepository,
        register_repository: type[CommunicationRegisterRepository] = (
            CommunicationRegisterRepository
        ),
        profile_repository: type[LanguageProfileRepository] = (
            LanguageProfileRepository
        ),
    ) -> None:
        self.user_repository = user_repository
        self.language_repository = language_repository
        self.register_repository = register_repository
        self.profile_repository = profile_repository

    def create(
        self,
        session: Session,
        user_id: uuid.UUID,
        data: LanguageProfileCreate,
    ) -> LanguageProfile:
        self._require_user(session, user_id)
        variant = self._resolve_variant(
            session,
            data.language_code,
            data.variant_code,
        )

        if self.profile_repository.exists_for_user_and_variant(
            session,
            user_id,
            variant.id,
        ):
            raise DuplicateLanguageProfileError(
                "the user already has a profile for this language variant"
            )

        production_register = self._resolve_register(
            session,
            data.default_production_register_code,
            mode="production",
        )
        comprehension_registers = self._resolve_registers(
            session,
            data.comprehension_register_codes,
            mode="comprehension",
        )

        profile = LanguageProfile(
            user_id=user_id,
            language_variant_id=variant.id,
            cefr_level=data.cefr_level,
            default_production_register_id=production_register.id,
        )
        profile.language_variant = variant
        profile.default_production_register = production_register
        profile.comprehension_registers = comprehension_registers

        self.profile_repository.add(session, profile)
        self._commit_profile_write(session)

        created = self.profile_repository.get_owned(
            session,
            user_id,
            profile.id,
        )
        assert created is not None
        return created

    def get(
        self,
        session: Session,
        user_id: uuid.UUID,
        profile_id: uuid.UUID,
    ) -> LanguageProfile:
        self._require_user(session, user_id)
        profile = self.profile_repository.get_owned(
            session,
            user_id,
            profile_id,
        )
        if profile is None:
            raise LanguageProfileNotFoundError(
                f"language profile {profile_id} was not found for user {user_id}"
            )
        return profile

    def list(
        self,
        session: Session,
        user_id: uuid.UUID,
    ) -> list[LanguageProfile]:
        self._require_user(session, user_id)
        return self.profile_repository.list_for_user(session, user_id)

    def update(
        self,
        session: Session,
        user_id: uuid.UUID,
        profile_id: uuid.UUID,
        data: LanguageProfileUpdate,
    ) -> LanguageProfile:
        profile = self.get(session, user_id, profile_id)

        if "language_code" in data.model_fields_set:
            assert data.language_code is not None
            assert data.variant_code is not None
            variant = self._resolve_variant(
                session,
                data.language_code,
                data.variant_code,
            )

            if (
                variant.id != profile.language_variant_id
                and self.profile_repository.exists_for_user_and_variant(
                    session,
                    user_id,
                    variant.id,
                    exclude_profile_id=profile.id,
                )
            ):
                raise DuplicateLanguageProfileError(
                    "the user already has a profile for this language variant"
                )

            profile.language_variant = variant
            profile.language_variant_id = variant.id

        if "cefr_level" in data.model_fields_set:
            assert data.cefr_level is not None
            profile.cefr_level = data.cefr_level

        if "default_production_register_code" in data.model_fields_set:
            assert data.default_production_register_code is not None
            production_register = self._resolve_register(
                session,
                data.default_production_register_code,
                mode="production",
            )
            profile.default_production_register = production_register
            profile.default_production_register_id = production_register.id

        if "comprehension_register_codes" in data.model_fields_set:
            assert data.comprehension_register_codes is not None
            profile.comprehension_registers = self._resolve_registers(
                session,
                data.comprehension_register_codes,
                mode="comprehension",
            )

        self._commit_profile_write(session)

        updated = self.profile_repository.get_owned(
            session,
            user_id,
            profile.id,
        )
        assert updated is not None
        return updated

    def _require_user(self, session: Session, user_id: uuid.UUID) -> None:
        if self.user_repository.get(session, user_id) is None:
            raise UserNotFoundError(f"user {user_id} was not found")

    def _resolve_variant(
        self,
        session: Session,
        language_code: str,
        variant_code: str,
    ) -> LanguageVariant:
        language = self.language_repository.get_by_code(session, language_code)
        if language is None:
            raise LanguageNotFoundError(
                f"language {language_code!r} was not found"
            )
        if not language.is_active:
            raise InactiveReferenceDataError(
                f"language {language_code!r} is inactive"
            )

        variant = self.language_repository.get_variant_by_code(
            session,
            variant_code,
        )
        if variant is None:
            raise LanguageVariantNotFoundError(
                f"language variant {variant_code!r} was not found"
            )
        if not variant.is_active:
            raise InactiveReferenceDataError(
                f"language variant {variant_code!r} is inactive"
            )
        if variant.language_id != language.id:
            raise LanguageVariantMismatchError(
                f"variant {variant_code!r} does not belong to language "
                f"{language_code!r}"
            )
        return variant

    def _resolve_register(
        self,
        session: Session,
        code: str,
        *,
        mode: str,
    ) -> CommunicationRegister:
        register = self.register_repository.get_by_code(session, code)
        if register is None:
            raise CommunicationRegisterNotFoundError(
                f"communication register {code!r} was not found"
            )
        self._validate_register(register, mode=mode)
        return register

    def _resolve_registers(
        self,
        session: Session,
        codes: list[str],
        *,
        mode: str,
    ) -> list[CommunicationRegister]:
        if not codes:
            return []

        registers = self.register_repository.get_by_codes(session, codes)
        by_code = {register.code: register for register in registers}

        resolved: list[CommunicationRegister] = []
        for code in codes:
            register = by_code.get(code)
            if register is None:
                raise CommunicationRegisterNotFoundError(
                    f"communication register {code!r} was not found"
                )
            self._validate_register(register, mode=mode)
            resolved.append(register)

        return resolved

    @staticmethod
    def _validate_register(
        register: CommunicationRegister,
        *,
        mode: str,
    ) -> None:
        if not register.is_active:
            raise InactiveReferenceDataError(
                f"communication register {register.code!r} is inactive"
            )

        if mode == "production" and not register.production_allowed:
            raise RegisterModeNotAllowedError(
                f"communication register {register.code!r} "
                "cannot be used for production"
            )

        if mode == "comprehension" and not register.comprehension_allowed:
            raise RegisterModeNotAllowedError(
                f"communication register {register.code!r} "
                "cannot be used for comprehension"
            )

    @staticmethod
    def _commit_profile_write(session: Session) -> None:
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            constraint_name = getattr(
                getattr(exc.orig, "diag", None),
                "constraint_name",
                None,
            )
            if constraint_name == _DUPLICATE_PROFILE_CONSTRAINT:
                raise DuplicateLanguageProfileError(
                    "the user already has a profile for this language variant"
                ) from exc
            raise
