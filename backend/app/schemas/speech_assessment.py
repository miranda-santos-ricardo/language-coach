"""Phase 7 assessment domain contracts (no persistence/provider integration).

These structures record provenance and limitations; they do not generate scores.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EvidenceKind(str, Enum):
    MEASURED = "MEASURED"
    MODEL_JUDGMENT = "MODEL_JUDGMENT"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"


class AssessmentStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FAILED = "FAILED"


class DimensionStatus(str, Enum):
    ASSESSED = "ASSESSED"
    NOT_ASSESSED = "NOT_ASSESSED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RetentionMode(str, Enum):
    EPHEMERAL = "EPHEMERAL"
    EXPLICIT_RETENTION = "EXPLICIT_RETENTION"


class AudioEvidence(StrictContract):
    recording_attempt_id: UUID
    mime_type: str = Field(min_length=3, max_length=100)
    size_bytes: int = Field(gt=0)
    duration_ms: int | None = Field(default=None, gt=0)
    sha256_hex: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    retention_mode: RetentionMode = RetentionMode.EPHEMERAL
    retention_consent: bool = False
    # A reference is NOT a filesystem path or URL; resolving it requires authorization.
    storage_reference: UUID | None = None

    @model_validator(mode="after")
    def enforce_retention_policy(self) -> "AudioEvidence":
        if self.retention_mode == RetentionMode.EXPLICIT_RETENTION and not self.retention_consent:
            raise ValueError("Explicit audio retention requires consent")
        if self.storage_reference is not None and self.retention_mode != RetentionMode.EXPLICIT_RETENTION:
            raise ValueError("Permanent storage reference is forbidden in ephemeral mode")
        return self


class AssessmentEvidence(StrictContract):
    evidence_id: UUID
    kind: EvidenceKind
    source: Literal["AUDIO", "STT", "SUBMITTED_TEXT", "CONVERSATION", "HUMAN"]
    description: str = Field(min_length=1, max_length=500)
    # A unit + method is required for actual numeric measurements.
    numeric_value: float | None = Field(default=None, allow_inf_nan=False)
    unit: str | None = Field(default=None, max_length=40)
    method: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def numeric_provenance(self) -> "AssessmentEvidence":
        if self.numeric_value is not None:
            if self.kind != EvidenceKind.MEASURED or not self.unit or not self.method:
                raise ValueError("Numeric measurements require MEASURED, unit and method")
        return self


class AssessmentDimension(StrictContract):
    name: Literal[
        "pronunciation_accuracy", "intelligibility", "prosody",
        "speaking_rate", "articulation_rate", "pausing",
        "relevance", "coherence", "professional_register", "clarity", "persuasiveness"
    ]
    status: DimensionStatus
    score: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    evidence_ids: list[UUID] = Field(default_factory=list)
    explanation: str = Field(min_length=1, max_length=2000)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def assessment_requires_evidence(self) -> "AssessmentDimension":
        if self.status != DimensionStatus.ASSESSED and (self.score is not None or self.evidence_ids):
            raise ValueError("Unassessed dimensions cannot have score or evidence IDs")
        if self.status == DimensionStatus.ASSESSED and not self.evidence_ids:
            raise ValueError("Assessed dimensions require supporting evidence")
        return self


class SpeechAssessment(StrictContract):
    assessment_id: UUID
    user_id: UUID
    language_profile_id: UUID
    practice_session_id: UUID
    conversation_turn_id: UUID
    client_request_id: UUID
    locale: str = Field(pattern=r"^[a-z]{2,3}-[A-Z]{2}$")
    cefr_level: Literal["A1", "A2", "B1", "B2", "C1", "C2"]
    scenario: str = Field(min_length=1, max_length=200)
    stt_transcript: str = Field(max_length=10000)
    submitted_text: str = Field(max_length=10000)
    audio: AudioEvidence | None = None
    status: AssessmentStatus
    evidence: list[AssessmentEvidence] = Field(default_factory=list)
    dimensions: list[AssessmentDimension] = Field(default_factory=list)
    rubric_version: str = Field(min_length=1, max_length=80)
    provider_version: str | None = Field(default=None, max_length=120)
    assessed_at: datetime | None = None
    failure_reason: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_evidence_graph(self) -> "SpeechAssessment":
        ids = [e.evidence_id for e in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate evidence IDs")
        known = set(ids)
        for d in self.dimensions:
            if not set(d.evidence_ids).issubset(known):
                raise ValueError("Dimension references unknown evidence")
            if d.name in {"pronunciation_accuracy", "intelligibility", "prosody", "pausing", "speaking_rate", "articulation_rate"} and d.status == DimensionStatus.ASSESSED:
                if self.audio is None:
                    raise ValueError("Speech/acoustic dimensions require original audio provenance")
                if not any(e.evidence_id in d.evidence_ids and e.source == "AUDIO" for e in self.evidence):
                    raise ValueError("Speech/acoustic dimensions require audio-derived evidence")
        if self.status == AssessmentStatus.COMPLETED and not any(d.status == DimensionStatus.ASSESSED for d in self.dimensions):
            raise ValueError("Completed assessment requires assessed dimension")
        return self
