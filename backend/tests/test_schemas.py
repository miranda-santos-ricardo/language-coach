import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models import (
    CEFRLevel,
    CommunicationRegister,
    Language,
    LanguageProfile,
    LanguageVariant,
)
from app.schemas import (
    LanguageProfileCreate,
    LanguageProfileRead,
    LanguageProfileUpdate,
    UserCreate,
)


def test_user_create_strips_display_name() -> None:
    schema = UserCreate(display_name="  Ricardo  ")

    assert schema.display_name == "Ricardo"


def test_user_create_rejects_blank_display_name() -> None:
    with pytest.raises(ValidationError):
        UserCreate(display_name="   ")


def test_language_profile_create_accepts_reference_codes() -> None:
    schema = LanguageProfileCreate(
        language_code="fr",
        variant_code="fr-CA",
        cefr_level="B2",
        default_production_register_code="professional",
        comprehension_register_codes=[
            "professional",
            "everyday",
            "colloquial",
        ],
    )

    assert schema.cefr_level is CEFRLevel.B2
    assert schema.variant_code == "fr-CA"
    assert schema.comprehension_register_codes[-1] == "colloquial"


def test_language_profile_create_rejects_invalid_cefr() -> None:
    with pytest.raises(ValidationError):
        LanguageProfileCreate(
            language_code="fr",
            variant_code="fr-CA",
            cefr_level="B3",
            default_production_register_code="professional",
            comprehension_register_codes=[],
        )


def test_language_profile_create_rejects_duplicate_comprehension_registers() -> None:
    with pytest.raises(
        ValidationError,
        match="comprehension register codes must be unique",
    ):
        LanguageProfileCreate(
            language_code="fr",
            variant_code="fr-CA",
            cefr_level="B2",
            default_production_register_code="professional",
            comprehension_register_codes=[
                "professional",
                "professional",
            ],
        )


def test_language_profile_create_rejects_invalid_register_code_format() -> None:
    with pytest.raises(ValidationError):
        LanguageProfileCreate(
            language_code="fr",
            variant_code="fr-CA",
            cefr_level="B2",
            default_production_register_code="Formal Executive",
            comprehension_register_codes=[],
        )


def test_language_profile_update_can_change_cefr_only() -> None:
    schema = LanguageProfileUpdate(cefr_level="C1")

    assert schema.cefr_level is CEFRLevel.C1
    assert schema.language_code is None


def test_language_profile_update_requires_language_and_variant_together() -> None:
    with pytest.raises(
        ValidationError,
        match="language_code and variant_code must be provided together",
    ):
        LanguageProfileUpdate(variant_code="fr-FR")


def test_language_profile_update_rejects_empty_patch() -> None:
    with pytest.raises(
        ValidationError,
        match="at least one field must be provided",
    ):
        LanguageProfileUpdate()



def test_language_profile_update_rejects_explicit_null() -> None:
    with pytest.raises(
        ValidationError,
        match="patch fields cannot be null",
    ):
        LanguageProfileUpdate(cefr_level=None)

def test_language_profile_update_allows_clearing_comprehension_registers() -> None:
    schema = LanguageProfileUpdate(comprehension_register_codes=[])

    assert schema.comprehension_register_codes == []


def test_language_profile_read_maps_orm_relationships_to_api_shape() -> None:
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    profile_id = uuid.uuid4()

    language = Language(
        code="fr",
        name="French",
        is_active=True,
    )
    variant = LanguageVariant(
        code="fr-CA",
        display_name="French — Canada / Québec",
        country_code="CA",
        regional_focus="Québec",
        is_active=True,
    )
    variant.language = language

    professional = CommunicationRegister(
        code="professional",
        display_name="Professional",
        production_allowed=True,
        comprehension_allowed=True,
        is_active=True,
    )
    colloquial = CommunicationRegister(
        code="colloquial",
        display_name="Colloquial",
        production_allowed=True,
        comprehension_allowed=True,
        is_active=True,
    )

    profile = LanguageProfile(
        id=profile_id,
        user_id=user_id,
        cefr_level=CEFRLevel.B2,
    )
    profile.language_variant = variant
    profile.default_production_register = professional
    profile.comprehension_registers = [professional, colloquial]
    profile.created_at = now
    profile.updated_at = now

    schema = LanguageProfileRead.model_validate(profile)

    assert schema.id == profile_id
    assert schema.language.code == "fr"
    assert schema.variant.code == "fr-CA"
    assert schema.variant.regional_focus == "Québec"
    assert schema.default_production_register.code == "professional"
    assert [register.code for register in schema.comprehension_registers] == [
        "professional",
        "colloquial",
    ]
