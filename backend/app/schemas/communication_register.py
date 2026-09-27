from pydantic import BaseModel, ConfigDict


class CommunicationRegisterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    display_name: str
    production_allowed: bool
    comprehension_allowed: bool
    is_active: bool
