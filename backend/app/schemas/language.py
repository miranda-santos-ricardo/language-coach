from pydantic import BaseModel, ConfigDict


class LanguageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    is_active: bool


class LanguageVariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    display_name: str
    country_code: str | None
    regional_focus: str | None
    is_active: bool
