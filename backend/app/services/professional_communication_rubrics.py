"""Phase 7 Step 5.2: versioned, non-scoring textual communication rubrics.

This module supplies review guidance, never independently evaluates submitted text.
No LLM, network, database, speech/phonetic assessment or CEFR inference.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from app.services.conversational_evidence import (
    DIMENSIONS, LOCALES, ConversationalEvidence, ConversationalEvidenceError,
    Dimension, DimensionObservation, accept_reviewed_observations,
    build_evidence_gate,
)

RUBRIC_VERSION = 'professional-communication-rubric-v1'
ScenarioType = Literal['executive_update', 'stakeholder_discussion', 'technical_explanation', 'general']


@dataclass(frozen=True)
class RubricCriterion:
    dimension: Dimension
    question: str
    positive_indicators: tuple[str, ...]
    limitations: tuple[str, ...]
    def __post_init__(self):
        if self.dimension not in DIMENSIONS or not self.question.strip():
            raise ConversationalEvidenceError('Invalid rubric criterion')
        if not self.positive_indicators or not self.limitations:
            raise ConversationalEvidenceError('Incomplete rubric guidance')


@dataclass(frozen=True)
class CommunicationRubric:
    version: str
    locale: str
    context: str
    scenario_type: ScenarioType
    criteria: tuple[RubricCriterion, ...]
    reviewer_instructions: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


_BASE: dict[Dimension, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    'relevance': (
        'Does the response address the stated communicative task?',
        ('Responds to the stated request', 'Identifies the relevant subject or decision'),
        ('Task instructions are necessary to judge relevance', 'Do not infer missing context from the response alone')),
    'coherence': (
        'Are the ideas related and ordered intelligibly?',
        ('Uses comprehensible transitions', 'Maintains a discernible line of reasoning'),
        ('Short or fragmentary submissions may not support this judgment', 'Do not mistake regional phrasing for incoherence')),
    'professional_register': (
        'Is the written language appropriate to the specified audience and situation?',
        ('Uses audience-appropriate wording', 'Handles technical terms with suitable explanation'),
        ('Formal register is not inherently superior', 'Do not penalize valid Canadian French or regional English variants')),
    'clarity': (
        'Can a reader understand the intended message from the submitted text?',
        ('Makes referents sufficiently clear', 'Expresses the main point with interpretable wording'),
        ('Text cannot establish speaking intelligibility', 'Do not penalize accent or audio delivery')),
    'persuasiveness': (
        'When a persuasive goal exists, are claims supported by reasons or relevant evidence?',
        ('Connects recommendation to a stated rationale', 'Addresses relevant concerns when the task calls for it'),
        ('A neutral informational answer need not persuade', 'Do not equate confident tone with evidential strength')),
}

_SCENARIOS: dict[str, tuple[str, ...]] = {
    'executive_update': ('Identify the decision, progress, or risk relevant to leadership.', 'Do not require persuasion when the task is only to inform.'),
    'stakeholder_discussion': ('Consider stakeholders and any explicit constraints.', 'Do not infer the audience’s reaction or satisfaction.'),
    'technical_explanation': ('Consider whether technical reasoning is tailored to the stated audience.', 'Do not assert technical accuracy without external verification.'),
    'general': ('Use the user-provided scenario and context.', 'Do not invent unstated audience, goals, or intent.'),
}


def get_communication_rubric(*, locale: str, context: str, scenario_type: str = 'general') -> CommunicationRubric:
    """Return a deterministic review rubric, not a learner assessment."""
    if locale not in LOCALES or context not in ('professional', 'conversational'):
        raise ConversationalEvidenceError('Unsupported locale or context')
    if scenario_type not in _SCENARIOS:
        raise ConversationalEvidenceError('Unsupported scenario type')
    criteria = tuple(RubricCriterion(d, *_BASE[d]) for d in DIMENSIONS)
    instructions = (
        'Review only the submitted text, the explicit scenario, and the stated task.',
        'Treat STT_UNEDITED, USER_EDITED, TYPED and VOICE_TEXT_UNKNOWN as distinct text provenance; never infer exact speech from text alone.',
        'Use direct, exact excerpts from submitted text for assessed dimensions; do not manufacture evidence.',
        'Abstain per dimension when evidence, task objective or audience is insufficient.',
        'Do not infer pronunciation, accent, speaking proficiency, CEFR, confidence or speaker identity.',
        'Do not reward verbosity or automatically penalize a concise response.',
        'Accept legitimate locale-specific spelling, vocabulary, syntax and professional communication conventions.',
        'These questions are review prompts, not calibrated scores or objective truth.',
        *(_SCENARIOS[scenario_type]),
        ('Professional suitability depends on audience, purpose and context; avoid blanket formality requirements.'
         if context == 'professional' else
         'Conversational language can appropriately use informal expressions and shortened turns.'),
    )
    return CommunicationRubric(RUBRIC_VERSION, locale, context, scenario_type, criteria, instructions)


@dataclass(frozen=True)
class RubricReviewSubmission:
    """Explicit observations produced by a qualified external reviewer; no automation here."""
    rubric_version: str
    scenario_type: ScenarioType
    evaluator_version: str
    reviewer_kind: Literal['HUMAN_REVIEWED', 'MODEL_JUDGMENT']
    observations: tuple[DimensionObservation, ...]


def validate_rubric_review(evidence: ConversationalEvidence, submission: RubricReviewSubmission):
    """Enforce rubric provenance and Step 5.1 review contracts.

    Important: quote presence checks are not independent adjudication of review accuracy.
    """
    if type(evidence) is not ConversationalEvidence or type(submission) is not RubricReviewSubmission:
        raise ConversationalEvidenceError('Invalid rubric review submission')
    if submission.rubric_version != RUBRIC_VERSION:
        raise ConversationalEvidenceError('Unrecognized rubric version')
    get_communication_rubric(locale=evidence.locale, context=evidence.context,
                             scenario_type=submission.scenario_type)
    gate = build_evidence_gate(evidence)
    if gate.status == 'INSUFFICIENT_EVIDENCE' and any(
            o.status in ('MODEL_JUDGMENT', 'HUMAN_REVIEWED') for o in submission.observations):
        raise ConversationalEvidenceError('Insufficient evidence for rubric review')
    if submission.reviewer_kind not in ('HUMAN_REVIEWED', 'MODEL_JUDGMENT'):
        raise ConversationalEvidenceError('Invalid reviewer provenance')
    # A persuasive observation is only applicable to a declared persuasive task;
    # neutral updates and descriptions must abstain unless the caller explicitly
    # supplies that goal in the scenario.
    for obs in submission.observations:
        if obs.dimension == 'persuasiveness' and obs.status in ('HUMAN_REVIEWED','MODEL_JUDGMENT'):
            if not any(token in evidence.scenario.lower() for token in (
                'persuad', 'convinc', 'argument', 'recommend', 'defend', 'propos', 'justif', 'convainc')):
                raise ConversationalEvidenceError('Persuasive goal not established by scenario')
    return accept_reviewed_observations(
        evidence, submission.observations,
        reviewer_kind=submission.reviewer_kind, evaluator_version=submission.evaluator_version)
