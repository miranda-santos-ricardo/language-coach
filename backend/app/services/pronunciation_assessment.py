"""Phase 7 Step 3: evidence-gated pronunciation provider boundary.

No network calls, model dependencies, phoneme inference, or recording retention.
The local fallback deliberately abstains from pronunciation scoring.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from app.schemas.speech_assessment import AssessmentDimension, DimensionStatus

SUPPORTED_LOCALES = frozenset({'fr-CA', 'en-CA', 'en-US', 'en-GB'})
MAX_AUDIO_BYTES = 10 * 1024 * 1024


class PronunciationRequestError(ValueError):
    """Rejected request; avoid including audio or transcript in error messages."""


class PronunciationOutcome(str, Enum):
    NOT_ASSESSED = 'NOT_ASSESSED'
    INSUFFICIENT_EVIDENCE = 'INSUFFICIENT_EVIDENCE'
    ASSESSED = 'ASSESSED'


@dataclass(frozen=True)
class PronunciationRequest:
    audio: bytes
    locale: str
    reference_text: str | None = None
    # This flag represents application-verified processing consent, not retention consent.
    processing_consent: bool = False

    def validate(self) -> None:
        if not self.processing_consent:
            raise PronunciationRequestError('Speech assessment requires explicit processing consent')
        if self.locale not in SUPPORTED_LOCALES:
            raise PronunciationRequestError('Unsupported locale')
        if not isinstance(self.audio, bytes) or not 0 < len(self.audio) <= MAX_AUDIO_BYTES:
            raise PronunciationRequestError('Invalid audio size or type')
        if self.reference_text is not None and (not self.reference_text.strip() or len(self.reference_text) > 10000):
            raise PronunciationRequestError('Invalid reference text')


@dataclass(frozen=True)
class PronunciationResult:
    outcome: PronunciationOutcome
    provider: str
    provider_version: str
    locale: str
    explanation: str
    limitations: tuple[str, ...]
    # Deliberately no score field: score-bearing adapters require a separately reviewed contract.

    def as_dimension(self) -> AssessmentDimension:
        if self.outcome == PronunciationOutcome.ASSESSED:
            raise ValueError('Cannot claim assessment without audio-based evidence references')
        return AssessmentDimension(
            name='pronunciation_accuracy',
            status=(DimensionStatus.INSUFFICIENT_EVIDENCE if self.outcome == PronunciationOutcome.INSUFFICIENT_EVIDENCE else DimensionStatus.NOT_ASSESSED),
            score=None,
            explanation=self.explanation,
            limitations=list(self.limitations),
        )


@runtime_checkable
class PronunciationAssessmentProvider(Protocol):
    """Future validated providers must fulfill this boundary without leaking raw audio."""

    def assess(self, request: PronunciationRequest) -> PronunciationResult: ...


class LocalEvidenceGateProvider:
    """Zero-cost offline baseline: verifies safe request, never fabricates accuracy."""

    def assess(self, request: PronunciationRequest) -> PronunciationResult:
        request.validate()
        return PronunciationResult(
            outcome=PronunciationOutcome.NOT_ASSESSED,
            provider='local-evidence-gate',
            provider_version='0.1',
            locale=request.locale,
            explanation='Pronunciation accuracy not assessed: no calibrated phonetic model is configured.',
            limitations=(
                'STT accuracy and acoustic activity cannot establish phoneme correctness.',
                'Regional pronunciation fairness has not been calibrated for this locale.',
                'No pronunciation score or intelligibility judgment is produced.',
            ),
        )


def make_default_pronunciation_provider() -> PronunciationAssessmentProvider:
    """Explicitly offline and free; never loads or silently enables a cloud provider."""
    return LocalEvidenceGateProvider()
