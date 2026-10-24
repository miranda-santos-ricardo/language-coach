"""Step 5.5.3: offline reviewer agreement and evaluator reliability evidence.

Independent human annotations are not manufactured or inferred from synthetic cases.
All comparisons require explicit, case-bound, versioned human decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from app.services.conversational_evidence import DIMENSIONS
from app.services.conversational_reference_bank import ReferenceCaseBank

Decision = Literal['ASSESS', 'ABSTAIN']
Quality = Literal['SUPPORTED', 'UNSUPPORTED', 'UNCERTAIN', 'NOT_REVIEWED']


class ReliabilityContractError(ValueError):
    pass


@dataclass(frozen=True)
class DimensionReview:
    dimension: str
    decision: Decision
    # Evidence correctness is separately reviewed, never inferred from substring matching.
    evidence_quality: Quality = 'NOT_REVIEWED'
    feedback_quality: Quality = 'NOT_REVIEWED'

    def __post_init__(self):
        if self.dimension not in DIMENSIONS or self.decision not in ('ASSESS', 'ABSTAIN'):
            raise ReliabilityContractError('Invalid dimension or decision')
        valid = ('SUPPORTED', 'UNSUPPORTED', 'UNCERTAIN', 'NOT_REVIEWED')
        if self.evidence_quality not in valid or self.feedback_quality not in valid:
            raise ReliabilityContractError('Invalid quality label')
        if self.decision == 'ABSTAIN' and (self.evidence_quality != 'NOT_REVIEWED' or
                                           self.feedback_quality != 'NOT_REVIEWED'):
            raise ReliabilityContractError('Cannot attach assessment quality to abstention')


@dataclass(frozen=True)
class HumanReview:
    case_id: str
    text_sha256: str
    reviewer_id: str
    rubric_version: str
    dimensions: tuple[DimensionReview, ...]
    independent: bool = True

    def __post_init__(self):
        if any(type(v) is not str or not v.strip() for v in
               (self.case_id, self.reviewer_id, self.rubric_version)):
            raise ReliabilityContractError('Missing review metadata')
        if len(self.text_sha256) != 64 or any(c not in '0123456789abcdef' for c in self.text_sha256):
            raise ReliabilityContractError('Invalid text digest')
        if type(self.dimensions) is not tuple or tuple(d.dimension for d in self.dimensions) != DIMENSIONS:
            raise ReliabilityContractError('Dimension order/coverage mismatch')
        if type(self.independent) is not bool:
            raise ReliabilityContractError('Invalid independence flag')


@dataclass(frozen=True)
class AdjudicatedReference:
    case_id: str
    text_sha256: str
    rubric_version: str
    source_reviewer_ids: tuple[str, ...]
    adjudicator_id: str
    dimensions: tuple[DimensionReview, ...]
    # Must be signed off outside the evaluator; not computed from a majority vote.
    approved: bool

    def __post_init__(self):
        if not self.case_id or not self.rubric_version or not self.adjudicator_id:
            raise ReliabilityContractError('Incomplete adjudication metadata')
        if len(self.text_sha256) != 64:
            raise ReliabilityContractError('Invalid digest')
        if len(set(self.source_reviewer_ids)) < 2 or len(self.source_reviewer_ids) != len(set(self.source_reviewer_ids)):
            raise ReliabilityContractError('At least two distinct reviewers required')
        if tuple(d.dimension for d in self.dimensions) != DIMENSIONS:
            raise ReliabilityContractError('Invalid adjudicated dimensions')
        if type(self.approved) is not bool:
            raise ReliabilityContractError('Invalid approval flag')


@dataclass(frozen=True)
class EvaluatorDimension:
    dimension: str
    decision: Decision
    evidence_quality: Quality = 'NOT_REVIEWED'
    feedback_quality: Quality = 'NOT_REVIEWED'

    def __post_init__(self):
        DimensionReview(self.dimension, self.decision, self.evidence_quality, self.feedback_quality)


@dataclass(frozen=True)
class EvaluatorObservation:
    case_id: str
    text_sha256: str
    evaluator_version: str
    dimensions: tuple[EvaluatorDimension, ...]

    def __post_init__(self):
        if not self.case_id or not self.evaluator_version or len(self.text_sha256) != 64:
            raise ReliabilityContractError('Invalid evaluator metadata')
        if tuple(d.dimension for d in self.dimensions) != DIMENSIONS:
            raise ReliabilityContractError('Invalid evaluator dimensions')


@dataclass(frozen=True)
class ReliabilityReport:
    bank_version: str
    total_cases: int
    independently_reviewed_cases: int
    adjudicated_cases: int
    compared_cases: int
    compared_dimensions: int
    decision_agreements: int
    semantic_evidence_compared: int
    semantic_evidence_agreements: int
    feedback_quality_compared: int
    feedback_quality_agreements: int
    reviewer_compared_dimensions: int
    reviewer_decision_agreements: int
    disagreements: tuple[tuple[str, str, str], ...]
    exclusions: tuple[tuple[str, str], ...]

    @property
    def decision_agreement_rate(self) -> float | None:
        return self.decision_agreements / self.compared_dimensions if self.compared_dimensions else None

    @property
    def reviewer_agreement_rate(self) -> float | None:
        return (self.reviewer_decision_agreements / self.reviewer_compared_dimensions
                if self.reviewer_compared_dimensions else None)

    @property
    def evidence_agreement_rate(self) -> float | None:
        return (self.semantic_evidence_agreements / self.semantic_evidence_compared
                if self.semantic_evidence_compared else None)

    @property
    def feedback_agreement_rate(self) -> float | None:
        return (self.feedback_quality_agreements / self.feedback_quality_compared
                if self.feedback_quality_compared else None)

    @property
    def release_ready(self) -> bool:
        return False


def text_digest(text: str) -> str:
    if type(text) is not str:
        raise ReliabilityContractError('Invalid text')
    return sha256(text.encode('utf-8')).hexdigest()


def analyze_reliability(bank: ReferenceCaseBank,
                        reviews: tuple[HumanReview, ...],
                        references: tuple[AdjudicatedReference, ...],
                        observations: tuple[EvaluatorObservation, ...]) -> ReliabilityReport:
    if type(bank) is not ReferenceCaseBank or any(type(x) is not tuple for x in
                                                    (reviews, references, observations)):
        raise ReliabilityContractError('Invalid reliability inputs')
    cases = {item.calibration.case_id: item.calibration for item in bank.cases}
    def assert_case(case_id: str, digest: str) -> None:
        if case_id not in cases or digest != text_digest(cases[case_id].text):
            raise ReliabilityContractError('Unknown case or mismatched source text')

    review_map: dict[str, list[HumanReview]] = {}
    seen_reviewers: set[tuple[str, str]] = set()
    for review in reviews:
        if type(review) is not HumanReview:
            raise ReliabilityContractError('Invalid human review')
        assert_case(review.case_id, review.text_sha256)
        key = review.case_id, review.reviewer_id
        if key in seen_reviewers:
            raise ReliabilityContractError('Duplicate reviewer')
        seen_reviewers.add(key)
        review_map.setdefault(review.case_id, []).append(review)
    references_map: dict[str, AdjudicatedReference] = {}
    for ref in references:
        if type(ref) is not AdjudicatedReference:
            raise ReliabilityContractError('Invalid reference')
        assert_case(ref.case_id, ref.text_sha256)
        if ref.case_id in references_map:
            raise ReliabilityContractError('Duplicate adjudication')
        source = review_map.get(ref.case_id, [])
        if not ref.approved or not set(ref.source_reviewer_ids).issubset({r.reviewer_id for r in source if r.independent}):
            raise ReliabilityContractError('Unapproved or ungrounded adjudication')
        if any(r.rubric_version != ref.rubric_version for r in source if r.reviewer_id in ref.source_reviewer_ids):
            raise ReliabilityContractError('Rubric mismatch')
        references_map[ref.case_id] = ref
    observations_map: dict[str, EvaluatorObservation] = {}
    for obs in observations:
        if type(obs) is not EvaluatorObservation:
            raise ReliabilityContractError('Invalid evaluator observation')
        assert_case(obs.case_id, obs.text_sha256)
        if obs.case_id in observations_map:
            raise ReliabilityContractError('Duplicate evaluator observation')
        observations_map[obs.case_id] = obs
    rcomp = ragree = dcomp = dagree = ecomp = eagree = fcomp = fagree = compared = 0
    discrepancies: list[tuple[str, str, str]] = []
    exclusions: list[tuple[str, str]] = []
    reviewed = 0
    for case_id in cases:
        humans = [r for r in review_map.get(case_id, []) if r.independent]
        if len(humans) >= 2:
            reviewed += 1
            first, second = humans[:2]
            if first.rubric_version == second.rubric_version:
                for a, b in zip(first.dimensions, second.dimensions):
                    rcomp += 1
                    ragree += a.decision == b.decision
            else:
                exclusions.append((case_id, 'REVIEWER_RUBRIC_MISMATCH'))
        ref = references_map.get(case_id)
        obs = observations_map.get(case_id)
        if not ref or not obs:
            exclusions.append((case_id, 'MISSING_APPROVED_REFERENCE' if not ref else 'MISSING_EVALUATOR_OBSERVATION'))
            continue
        compared += 1
        for human, model in zip(ref.dimensions, obs.dimensions):
            dcomp += 1
            if human.decision == model.decision:
                dagree += 1
            else:
                discrepancies.append((case_id, human.dimension, 'ASSESS_ABSTAIN_DISAGREEMENT'))
            if human.decision == model.decision == 'ASSESS':
                if human.evidence_quality != 'NOT_REVIEWED' and model.evidence_quality != 'NOT_REVIEWED':
                    ecomp += 1
                    if human.evidence_quality == model.evidence_quality:
                        eagree += 1
                    else:
                        discrepancies.append((case_id, human.dimension, 'EVIDENCE_QUALITY_DISAGREEMENT'))
                if human.feedback_quality != 'NOT_REVIEWED' and model.feedback_quality != 'NOT_REVIEWED':
                    fcomp += 1
                    if human.feedback_quality == model.feedback_quality:
                        fagree += 1
                    else:
                        discrepancies.append((case_id, human.dimension, 'FEEDBACK_QUALITY_DISAGREEMENT'))
    return ReliabilityReport(bank.version, len(cases), reviewed, len(references_map), compared,
                             dcomp, dagree, ecomp, eagree, fcomp, fagree, rcomp, ragree,
                             tuple(discrepancies), tuple(exclusions))
