"""Phase 7 Step 5.1: conservative conversational-evaluation evidence contracts.

No LLM calls, scores, CEFR inference, storage, or audio processing.
Authorization/ownership checks are the responsibility of the authenticated caller.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal
from uuid import UUID

Locale = Literal['fr-CA', 'en-CA', 'en-US', 'en-GB']
Context = Literal['professional', 'conversational']
TextOrigin = Literal['STT_UNEDITED', 'USER_EDITED', 'TYPED', 'VOICE_TEXT_UNKNOWN']
Dimension = Literal['relevance', 'coherence', 'professional_register', 'clarity', 'persuasiveness']

DIMENSIONS: tuple[Dimension, ...] = (
    'relevance', 'coherence', 'professional_register', 'clarity', 'persuasiveness'
)
LOCALES = ('fr-CA', 'en-CA', 'en-US', 'en-GB')
MAX_TEXT = 10000


class ConversationalEvidenceError(ValueError):
    """Safe, input-independent contract validation error."""


@dataclass(frozen=True)
class ConversationalEvidence:
    user_id: UUID
    practice_session_id: UUID
    conversation_turn_id: UUID
    client_request_id: UUID
    locale: Locale
    context: Context
    scenario: str
    text: str
    origin: TextOrigin
    # True means trusted caller verified that this exact turn belongs to this user/session.
    authorized_turn: bool
    # Explicitly distinguishes text submitted after possible STT edits from spoken words.
    stt_original_available: bool = False

    def __post_init__(self) -> None:
        for name in ('user_id', 'practice_session_id', 'conversation_turn_id', 'client_request_id'):
            if type(getattr(self, name)) is not UUID:
                raise ConversationalEvidenceError('Invalid identity reference')
        if self.locale not in LOCALES or self.context not in ('professional', 'conversational'):
            raise ConversationalEvidenceError('Unsupported locale or context')
        if self.origin not in ('STT_UNEDITED', 'USER_EDITED', 'TYPED', 'VOICE_TEXT_UNKNOWN'):
            raise ConversationalEvidenceError('Unsupported text origin')
        if type(self.authorized_turn) is not bool or not self.authorized_turn:
            raise ConversationalEvidenceError('Authenticated turn ownership required')
        if type(self.stt_original_available) is not bool:
            raise ConversationalEvidenceError('Invalid STT provenance flag')
        if type(self.text) is not str or not self.text.strip() or len(self.text) > MAX_TEXT:
            raise ConversationalEvidenceError('Unusable submitted text')
        if type(self.scenario) is not str or not self.scenario.strip() or len(self.scenario) > 200:
            raise ConversationalEvidenceError('Invalid scenario')
        if self.origin == 'STT_UNEDITED' and not self.stt_original_available:
            raise ConversationalEvidenceError('Unedited STT requires STT provenance')
        if self.origin in ('TYPED', 'VOICE_TEXT_UNKNOWN') and self.stt_original_available:
            raise ConversationalEvidenceError('Unverified voice or typed text cannot claim STT original')


@dataclass(frozen=True)
class DimensionObservation:
    dimension: Dimension
    status: Literal['NOT_ASSESSED', 'INSUFFICIENT_EVIDENCE', 'HUMAN_REVIEWED', 'MODEL_JUDGMENT']
    explanation: str
    # A quote must occur exactly in submitted text (not in instructions or scenario).
    supporting_quote: str | None = None
    def __post_init__(self) -> None:
        if self.dimension not in DIMENSIONS:
            raise ConversationalEvidenceError('Unknown dimension')
        if self.status not in ('NOT_ASSESSED', 'INSUFFICIENT_EVIDENCE', 'HUMAN_REVIEWED', 'MODEL_JUDGMENT'):
            raise ConversationalEvidenceError('Unknown observation status')
        if type(self.explanation) is not str or not self.explanation.strip() or len(self.explanation) > 1000:
            raise ConversationalEvidenceError('Invalid explanation')
        if self.supporting_quote is not None and (type(self.supporting_quote) is not str or not self.supporting_quote.strip() or len(self.supporting_quote) > 500):
            raise ConversationalEvidenceError('Invalid supporting quote')
        if self.status in ('NOT_ASSESSED', 'INSUFFICIENT_EVIDENCE') and self.supporting_quote is not None:
            raise ConversationalEvidenceError('Unassessed dimensions cannot claim supporting quotes')
        if self.status in ('MODEL_JUDGMENT', 'HUMAN_REVIEWED') and self.supporting_quote is None:
            raise ConversationalEvidenceError('Assessed dimensions require explicit quoted evidence')


@dataclass(frozen=True)
class ConversationalAssessmentDraft:
    schema_version: str
    locale: Locale
    context: Context
    text_origin: TextOrigin
    status: Literal['INSUFFICIENT_EVIDENCE', 'AWAITING_EVALUATOR', 'REVIEWED']
    dimensions: tuple[DimensionObservation, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def build_evidence_gate(evidence: ConversationalEvidence) -> ConversationalAssessmentDraft:
    """Return safe baseline, never infer evaluation solely from text length or style."""
    if type(evidence) is not ConversationalEvidence:
        raise ConversationalEvidenceError('Expected verified evidence contract')
    insufficient = len(evidence.text.split()) < 4
    status = 'INSUFFICIENT_EVIDENCE' if insufficient else 'AWAITING_EVALUATOR'
    dims = tuple(DimensionObservation(d, 'INSUFFICIENT_EVIDENCE' if insufficient else 'NOT_ASSESSED',
                                     'Insufficient text for conversational review.' if insufficient else 'Not evaluated; qualified review is required.')
                 for d in DIMENSIONS)
    limits = ('Submitted text is not proof of exact spoken wording or pronunciation.',
              'No automated competence, CEFR, persuasion, or professional-register score is inferred.',
              'Context relevance and interpretation require qualified review.',
              'Ownership flag is caller-attested; application must enforce authenticated authorization.')
    return ConversationalAssessmentDraft('conversational-evidence-v1', evidence.locale, evidence.context,
                                         evidence.origin, status, dims, limits)


def accept_reviewed_observations(evidence: ConversationalEvidence, observations: tuple[DimensionObservation, ...],
                                 *, reviewer_kind: Literal['HUMAN_REVIEWED', 'MODEL_JUDGMENT'],
                                 evaluator_version: str) -> ConversationalAssessmentDraft:
    """Validate provenance of outside review; DOES NOT verify review quality or calibration."""
    if type(evidence) is not ConversationalEvidence:
        raise ConversationalEvidenceError('Expected verified evidence contract')
    if reviewer_kind not in ('HUMAN_REVIEWED', 'MODEL_JUDGMENT'):
        raise ConversationalEvidenceError('Unsupported review provenance')
    if type(evaluator_version) is not str or not evaluator_version.strip() or len(evaluator_version) > 120:
        raise ConversationalEvidenceError('Evaluator version required')
    if type(observations) is not tuple or len(observations) != len(DIMENSIONS):
        raise ConversationalEvidenceError('Exactly one entry per dimension required')
    if any(type(o) is not DimensionObservation for o in observations):
        raise ConversationalEvidenceError('Invalid dimension observation')
    if tuple(o.dimension for o in observations) != DIMENSIONS:
        raise ConversationalEvidenceError('Dimensions must follow stable contract order')
    if any(o.status not in (reviewer_kind, 'INSUFFICIENT_EVIDENCE', 'NOT_ASSESSED') for o in observations):
        raise ConversationalEvidenceError('Reviewer provenance mismatch')
    for obs in observations:
        if obs.supporting_quote is not None and obs.supporting_quote not in evidence.text:
            raise ConversationalEvidenceError('Quoted evidence must occur in submitted text')
    if len(evidence.text.split()) < 4 and any(o.status == reviewer_kind for o in observations):
        raise ConversationalEvidenceError('Insufficient text cannot be marked assessed')
    reviewed = any(o.status == reviewer_kind for o in observations)
    return ConversationalAssessmentDraft('conversational-evidence-v1', evidence.locale, evidence.context,
        evidence.origin, 'REVIEWED' if reviewed else 'INSUFFICIENT_EVIDENCE', observations,
        ('This review concerns submitted text, not acoustic performance or exact spoken words.',
         f'External review provenance declared: {reviewer_kind}; evaluator: {evaluator_version}.',
         'Quoted evidence is presence-checked, not independently verified as accurate or appropriate.',
         'No calibrated CEFR level or numeric proficiency score is produced.'))
