import uuid

import pytest
from sqlalchemy.orm import Session

from app.models import CEFRLevel, CommunicationRegister
from app.schemas import LanguageProfileCreate, LanguageProfileUpdate, UserCreate
from app.services import (
    CommunicationRegisterNotFoundError,
    CommunicationRegisterService,
    DuplicateLanguageProfileError,
    LanguageProfileNotFoundError,
    LanguageService,
    LanguageVariantMismatchError,
    LanguageVariantNotFoundError,
    RegisterModeNotAllowedError,
    UserNotFoundError,
    UserService,
)
from app.services.language_profile import LanguageProfileService


def _create_user(session: Session, name: str = "Ricardo"):
    return UserService().create(session, UserCreate(display_name=name))


def _profile_payload(
    *,
    language_code: str = "fr",
    variant_code: str = "fr-CA",
    cefr_level: str = "B2",
    production: str = "professional",
    comprehension: list[str] | None = None,
) -> LanguageProfileCreate:
    return LanguageProfileCreate(
        language_code=language_code,
        variant_code=variant_code,
        cefr_level=cefr_level,
        default_production_register_code=production,
        comprehension_register_codes=(
            comprehension
            if comprehension is not None
            else ["professional", "everyday", "colloquial"]
        ),
    )


def test_user_service_creates_retrieves_and_lists_users(
    service_session: Session,
) -> None:
    service = UserService()

    ricardo = service.create(
        service_session,
        UserCreate(display_name="Ricardo"),
    )
    alice = service.create(
        service_session,
        UserCreate(display_name="Alice"),
    )

    assert service.get(service_session, ricardo.id).display_name == "Ricardo"
    assert [user.display_name for user in service.list(service_session)] == [
        "Alice",
        "Ricardo",
    ]
    assert alice.id != ricardo.id


def test_user_service_rejects_unknown_user(service_session: Session) -> None:
    with pytest.raises(UserNotFoundError):
        UserService().get(service_session, uuid.uuid4())


def test_language_service_lists_active_languages_and_variants(
    service_session: Session,
) -> None:
    service = LanguageService()

    assert [language.code for language in service.list(service_session)] == [
        "en",
        "fr",
    ]
    assert [
        variant.code
        for variant in service.list_variants(service_session, "fr")
    ] == ["fr-CA", "fr-FR"]


def test_language_profile_service_creates_and_retrieves_profile(
    service_session: Session,
) -> None:
    user = _create_user(service_session)
    service = LanguageProfileService()

    created = service.create(
        service_session,
        user.id,
        _profile_payload(),
    )
    retrieved = service.get(service_session, user.id, created.id)

    assert retrieved.id == created.id
    assert retrieved.language_variant.code == "fr-CA"
    assert retrieved.language_variant.language.code == "fr"
    assert retrieved.cefr_level is CEFRLevel.B2
    assert retrieved.default_production_register.code == "professional"
    assert {r.code for r in retrieved.comprehension_registers} == {
        "professional",
        "everyday",
        "colloquial",
    }


def test_language_profile_service_rejects_unknown_variant(
    service_session: Session,
) -> None:
    user = _create_user(service_session)

    with pytest.raises(LanguageVariantNotFoundError):
        LanguageProfileService().create(
            service_session,
            user.id,
            _profile_payload(variant_code="fr-BE"),
        )


def test_language_profile_service_rejects_language_variant_mismatch(
    service_session: Session,
) -> None:
    user = _create_user(service_session)

    with pytest.raises(LanguageVariantMismatchError):
        LanguageProfileService().create(
            service_session,
            user.id,
            _profile_payload(language_code="en", variant_code="fr-CA"),
        )


def test_language_profile_service_rejects_duplicate_profile(
    service_session: Session,
) -> None:
    user = _create_user(service_session)
    service = LanguageProfileService()
    service.create(service_session, user.id, _profile_payload())

    with pytest.raises(DuplicateLanguageProfileError):
        service.create(service_session, user.id, _profile_payload())


def test_user_can_have_profiles_for_different_variants(
    service_session: Session,
) -> None:
    user = _create_user(service_session)
    service = LanguageProfileService()

    service.create(service_session, user.id, _profile_payload())
    service.create(
        service_session,
        user.id,
        _profile_payload(variant_code="fr-FR", cefr_level="B1"),
    )
    service.create(
        service_session,
        user.id,
        _profile_payload(
            language_code="en",
            variant_code="en-CA",
            cefr_level="C1",
        ),
    )

    profiles = service.list(service_session, user.id)

    assert {profile.language_variant.code for profile in profiles} == {
        "fr-CA",
        "fr-FR",
        "en-CA",
    }


def test_profile_ownership_prevents_cross_user_access(
    service_session: Session,
) -> None:
    owner = _create_user(service_session, "Owner")
    other_user = _create_user(service_session, "Other")
    service = LanguageProfileService()
    profile = service.create(service_session, owner.id, _profile_payload())

    with pytest.raises(LanguageProfileNotFoundError):
        service.get(service_session, other_user.id, profile.id)


def test_profile_update_changes_cefr_registers_and_variant(
    service_session: Session,
) -> None:
    user = _create_user(service_session)
    service = LanguageProfileService()
    profile = service.create(service_session, user.id, _profile_payload())

    updated = service.update(
        service_session,
        user.id,
        profile.id,
        LanguageProfileUpdate(
            language_code="fr",
            variant_code="fr-FR",
            cefr_level="C1",
            default_production_register_code="colloquial",
            comprehension_register_codes=["colloquial", "conversational"],
        ),
    )

    assert updated.language_variant.code == "fr-FR"
    assert updated.cefr_level is CEFRLevel.C1
    assert updated.default_production_register.code == "colloquial"
    assert {r.code for r in updated.comprehension_registers} == {
        "colloquial",
        "conversational",
    }


def test_profile_update_can_clear_comprehension_registers(
    service_session: Session,
) -> None:
    user = _create_user(service_session)
    service = LanguageProfileService()
    profile = service.create(service_session, user.id, _profile_payload())

    updated = service.update(
        service_session,
        user.id,
        profile.id,
        LanguageProfileUpdate(comprehension_register_codes=[]),
    )

    assert updated.comprehension_registers == []


def test_profile_update_rejects_variant_that_is_already_owned(
    service_session: Session,
) -> None:
    user = _create_user(service_session)
    service = LanguageProfileService()
    first = service.create(service_session, user.id, _profile_payload())
    service.create(
        service_session,
        user.id,
        _profile_payload(variant_code="fr-FR"),
    )

    with pytest.raises(DuplicateLanguageProfileError):
        service.update(
            service_session,
            user.id,
            first.id,
            LanguageProfileUpdate(
                language_code="fr",
                variant_code="fr-FR",
            ),
        )


def test_profile_service_rejects_unknown_comprehension_register(
    service_session: Session,
) -> None:
    user = _create_user(service_session)

    with pytest.raises(CommunicationRegisterNotFoundError):
        LanguageProfileService().create(
            service_session,
            user.id,
            _profile_payload(comprehension=["professional", "academic"]),
        )


def test_profile_service_enforces_register_mode_capability(
    service_session: Session,
) -> None:
    service_session.add(
        CommunicationRegister(
            code="listening_only",
            display_name="Listening Only",
            production_allowed=False,
            comprehension_allowed=True,
            is_active=True,
        )
    )
    service_session.commit()
    user = _create_user(service_session)

    with pytest.raises(RegisterModeNotAllowedError):
        LanguageProfileService().create(
            service_session,
            user.id,
            _profile_payload(production="listening_only"),
        )


def test_communication_register_service_lists_active_registers(
    service_session: Session,
) -> None:
    registers = CommunicationRegisterService().list(service_session)

    assert [register.code for register in registers] == [
        "colloquial",
        "conversational",
        "everyday",
        "formal_executive",
        "professional",
    ]
