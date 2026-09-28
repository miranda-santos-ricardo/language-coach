import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CEFRLevel, SessionStatus, TrainingMode


class PracticeSessionCreate(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True
    )

    training_mode: TrainingMode
    register_code: str = Field(alias="register", min_length=1, max_length=50)
    target_cefr: CEFRLevel | None = None
    scenario_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )


class PracticeSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True,populate_by_name=True)

    id: uuid.UUID
    language_profile_id: uuid.UUID

    training_mode: TrainingMode

    register_code: str = Field(alias="register")

    profile_cefr: CEFRLevel
    target_cefr: CEFRLevel | None
    effective_cefr: CEFRLevel

    language: str
    variant: str

    scenario_key: str | None

    status: SessionStatus

    started_at: datetime
    ended_at: datetime | None

    created_at: datetime
    updated_at: datetime