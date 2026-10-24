"""Phase 7 Step 5.5.5: offline quality evidence closure, not production authorization.

The report intentionally refuses to infer semantic accuracy or release readiness from
synthetic cases, mocked calls, or absent independently adjudicated human reviews.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.conversational_reference_bank import ReferenceCaseBank, bank_coverage
from app.services.conversational_reliability import (
    HumanReview, AdjudicatedReference, EvaluatorObservation,
    analyze_reliability, ReliabilityContractError,
)
from app.services.conversational_bias_analysis import analyze_bias_and_failures

REQUIRED_EVIDENCE = (
    'INDEPENDENT_HUMAN_REVIEW',
    'ADJUDICATED_HUMAN_REFERENCES',
    'FROZEN_EVALUATOR_OBSERVATIONS',
    'SEMANTIC_EVIDENCE_REVIEW',
    'FEEDBACK_QUALITY_REVIEW',
    'REGIONAL_AND_REGISTER_COVERAGE',
)
EXTERNAL_RELEASE_GATES = (
    'POSTGRESQL_CONCURRENCY_VALIDATED',
    'REAL_OIDC_PROVIDER_VALIDATED',
    'OPERATIONAL_SECURITY_CONTROLS_VERIFIED',
    'EXPLICIT_HUMAN_RELEASE_APPROVAL',
)


@dataclass(frozen=True)
class QualityClosureReport:
    bank_version: str
    case_count: int
    reference_status: str
    reviewed_cases: int
    adjudicated_cases: int
    compared_cases: int
    decision_agreement_rate: float | None
    evidence_agreement_rate: float | None
    feedback_agreement_rate: float | None
    slice_count: int
    unmet_evidence: tuple[str, ...]
    external_release_gates: tuple[str, ...]
    decision: str = 'NOT_VALIDATED_FOR_RELEASE'

    @property
    def release_ready(self) -> bool:
        return False

    def as_dict(self) -> dict[str, object]:
        return {
            'bank_version': self.bank_version,
            'case_count': self.case_count,
            'reference_status': self.reference_status,
            'reviewed_cases': self.reviewed_cases,
            'adjudicated_cases': self.adjudicated_cases,
            'compared_cases': self.compared_cases,
            'decision_agreement_rate': self.decision_agreement_rate,
            'evidence_agreement_rate': self.evidence_agreement_rate,
            'feedback_agreement_rate': self.feedback_agreement_rate,
            'slice_count': self.slice_count,
            'unmet_evidence': list(self.unmet_evidence),
            'external_release_gates': list(self.external_release_gates),
            'decision': self.decision,
            'release_ready': self.release_ready,
        }


def close_conversational_quality(
    bank: ReferenceCaseBank,
    reviews: tuple[HumanReview, ...] = (),
    references: tuple[AdjudicatedReference, ...] = (),
    observations: tuple[EvaluatorObservation, ...] = (),
) -> QualityClosureReport:
    """Validate evidence and describe gaps. Never approve a production release."""
    if type(bank) is not ReferenceCaseBank:
        raise ReliabilityContractError('Expected validated reference bank')
    reliability = analyze_reliability(bank, reviews, references, observations)
    failures = analyze_bias_and_failures(bank, reviews, references, observations)
    coverage = bank_coverage(bank)
    unmet: list[str] = []
    if reliability.independently_reviewed_cases < len(bank.cases):
        unmet.append('INDEPENDENT_HUMAN_REVIEW')
    if reliability.adjudicated_cases < len(bank.cases):
        unmet.append('ADJUDICATED_HUMAN_REFERENCES')
    if reliability.compared_cases < len(bank.cases):
        unmet.append('FROZEN_EVALUATOR_OBSERVATIONS')
    if not reliability.semantic_evidence_compared:
        unmet.append('SEMANTIC_EVIDENCE_REVIEW')
    if not reliability.feedback_quality_compared:
        unmet.append('FEEDBACK_QUALITY_REVIEW')
    if not (coverage['required_locale_coverage'] and coverage['required_scenario_coverage']):
        unmet.append('REGIONAL_AND_REGISTER_COVERAGE')
    # Counts and agreement rates alone do not establish representative sampling,
    # statistical adequacy, or educational effectiveness.
    return QualityClosureReport(
        bank_version=bank.version,
        case_count=len(bank.cases),
        reference_status=bank.reference_status,
        reviewed_cases=reliability.independently_reviewed_cases,
        adjudicated_cases=reliability.adjudicated_cases,
        compared_cases=reliability.compared_cases,
        decision_agreement_rate=reliability.decision_agreement_rate,
        evidence_agreement_rate=reliability.evidence_agreement_rate,
        feedback_agreement_rate=reliability.feedback_agreement_rate,
        slice_count=len(failures.slices),
        unmet_evidence=tuple(unmet),
        external_release_gates=EXTERNAL_RELEASE_GATES,
    )
