import uuid
from datetime import datetime

from pydantic import AliasPath, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import CEFRLevel
from app.schemas.common import (
    CommunicationRegisterCode,
    LanguageCode,
    LanguageVariantCode,
)
from app.schemas.communication_register import CommunicationRegisterRead
from app.schemas.language import LanguageRead, LanguageVariantRead


def _validate_unique_register_codes(values: list[str]) -> list[str]:
    if len(values) != len(set(values)):
        raise ValueError("comprehension register codes must be unique")
    return values


class LanguageProfileCreate(BaseModel):
    language_code: LanguageCode
    variant_code: LanguageVariantCode
    cefr_level: CEFRLevel
    default_production_register_code: CommunicationRegisterCode
    comprehension_register_codes: list[CommunicationRegisterCode] = Field(
        default_factory=list,
    )

    @field_validator("comprehension_register_codes")
    @classmethod
    def validate_unique_comprehension_registers(
        cls,
        values: list[str],
    ) -> list[str]:
        return _validate_unique_register_codes(values)


class LanguageProfileUpdate(BaseModel):
    language_code: LanguageCode | None = None
    variant_code: LanguageVariantCode | None = None
    cefr_level: CEFRLevel | None = None
    default_production_register_code: CommunicationRegisterCode | None = None
    comprehension_register_codes: list[CommunicationRegisterCode] | None = None

    @field_validator(
        "language_code",
        "variant_code",
        "cefr_level",
        "default_production_register_code",
        "comprehension_register_codes",
        mode="before",
    )
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("patch fields cannot be null")
        return value

    @field_validator("comprehension_register_codes")
    @classmethod
    def validate_unique_comprehension_registers(
        cls,
        values: list[str] | None,
    ) -> list[str] | None:
        if values is None:
            return None
        return _validate_unique_register_codes(values)

    @model_validator(mode="after")
    def validate_patch_semantics(self) -> "LanguageProfileUpdate":
        language_was_sent = "language_code" in self.model_fields_set
        variant_was_sent = "variant_code" in self.model_fields_set

        if language_was_sent != variant_was_sent:
            raise ValueError(
                "language_code and variant_code must be provided together"
            )

        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")

        return self


class LanguageProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    language: LanguageRead = Field(
        validation_alias=AliasPath("language_variant", "language"),
    )
    variant: LanguageVariantRead = Field(
        validation_alias="language_variant",
    )
    cefr_level: CEFRLevel
    default_production_register: CommunicationRegisterRead
    comprehension_registers: list[CommunicationRegisterRead]
    created_at: datetime
    updated_at: datetime
