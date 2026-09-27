import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.common import DisplayName


class UserCreate(BaseModel):
    display_name: DisplayName


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    created_at: datetime
    updated_at: datetime
