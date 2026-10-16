"""HTTP request/response contract for submitting a learner conversation turn."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.structured_feedback import StructuredLanguageFeedback


class ConversationTurnSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1, max_length=4000)
    input_modality: Literal["text", "voice"]
    client_request_id: uuid.UUID = Field(strict=False)


class ConversationTurnSubmitted(BaseModel):
    turn_id: uuid.UUID
    turn_index: int
    coach_response: str
    feedback: StructuredLanguageFeedback
    replayed: bool
    prompt_version: str | None = None
    model: str | None = None


class ConversationTurnDetail(BaseModel):
    """Persisted turn and feedback (also used for items in the history response)."""
    model_config = ConfigDict(from_attributes=True)
    turn_id: uuid.UUID
    turn_index: int
    input_modality: Literal["text", "voice"]
    learner_text: str
    coach_response: str
    created_at: datetime
    feedback: StructuredLanguageFeedback


class ConversationTurnPage(BaseModel):
    items: list[ConversationTurnDetail]
    limit: int
    offset: int


def persisted_turn_response(turn) -> ConversationTurnDetail:
    """Use the existing strict feedback schema, including its `register` alias."""
    from app.services.conversation_service import ConversationService
    output = ConversationService._restore_output(turn)
    return ConversationTurnDetail(
        turn_id=turn.id, turn_index=turn.turn_index,
        input_modality=turn.input_modality, learner_text=turn.learner_text,
        coach_response=turn.coach_response, created_at=turn.created_at,
        feedback=output.feedback,
    )
