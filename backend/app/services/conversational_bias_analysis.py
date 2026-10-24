"""Step 5.5.4: offline, descriptive failure slicing; no protected-trait inference.

No statistical bias/discrimination claim follows from a small synthetic case bank.
Human-comparison rates are exposed only for valid adjudicated references.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.conversational_reference_bank import ReferenceCaseBank
from app.services.conversational_reliability import (
    AdjudicatedReference, EvaluatorObservation, HumanReview,
    ReliabilityContractError, analyze_reliability, text_digest,
)

SliceField = Literal['locale', 'context', 'scenario_type', 'origin', 'challenge_tag', 'length_band']
SLICE_FIELDS = ('locale', 'context', 'scenario_type', 'origin', 'challenge_tag', 'length_band')


@dataclass(frozen=True)
class FailureSlice:
    field: str
    value: str
    case_count: int
    observed_cases: int
    approved_reference_cases: int
    compared_cases: int
    compared_dimensions: int
    decision_agreements: int
    model_abstentions: int
    human_required_abstentions: int
    false_assessments: int
    missed_assessments: int
    unsupported_evidence_flags: int
    unsupported_feedback_flags: int
    disagreement_count: int
    exclusions: tuple[tuple[str, str], ...]
    # Small, nonrandom synthetic slices are descriptive only, never pass/fail metrics.
    descriptive_only: bool = True

    @property
    def decision_agreement_rate(self) -> float | None:
        return self.decision_agreements / self.compared_dimensions if self.compared_dimensions else None

    @property
    def observed_abstention_rate(self) -> float | None:
        return self.model_abstentions / (self.observed_cases * 5) if self.observed_cases else None


@dataclass(frozen=True)
class FailureAnalysisReport:
    bank_version: str
    evaluator_versions: tuple[str, ...]
    cases: int
    observations: int
    references: int
    slices: tuple[FailureSlice, ...]
    gap_hypotheses: tuple[str, ...]
    methodology: str = 'DESCRIPTIVE_SYNTHETIC_NOT_BIAS_PROOF'
    release_ready: bool = False


def _band(text: str) -> str:
    n = len(text.split())
    return 'SHORT_LT_4' if n < 4 else ('MEDIUM_4_TO_24' if n < 25 else 'LONG_25_PLUS')


def _slice_values(item) -> dict[str, tuple[str, ...]]:
    c = item.calibration
    return {
        'locale': (c.locale,), 'context': (c.context,),
        'scenario_type': (c.scenario_type,), 'origin': (c.origin,),
        'challenge_tag': item.challenge_tags, 'length_band': (_band(c.text),),
    }


def analyze_bias_and_failures(
    bank: ReferenceCaseBank,
    reviews: tuple[HumanReview, ...] = (),
    references: tuple[AdjudicatedReference, ...] = (),
    observations: tuple[EvaluatorObservation, ...] = (),
    *, min_comparable_cases_for_hypothesis: int = 3,
) -> FailureAnalysisReport:
    """Group validated reliability evidence without manufacturing human labels.

    Identical cases can occur in multiple *different* slice dimensions; slice counts
    must not be summed across dimensions. No p-values or parity claims are produced.
    """
    if type(min_comparable_cases_for_hypothesis) is not int or min_comparable_cases_for_hypothesis < 2:
        raise ReliabilityContractError('Invalid minimum comparable cases')
    # Reuse the strict case / reviewer / adjudication validation of Step 5.5.3.
    analyze_reliability(bank, reviews, references, observations)
    case_map = {x.calibration.case_id: x for x in bank.cases}
    obs_map = {x.case_id: x for x in observations}
    ref_map = {x.case_id: x for x in references}
    groups: dict[tuple[str, str], set[str]] = {}
    for case_id, item in case_map.items():
        for field, vals in _slice_values(item).items():
            for value in vals:
                groups.setdefault((field, value), set()).add(case_id)
    results: list[FailureSlice] = []
    for (field, value), case_ids in sorted(groups.items()):
        sub_cases = len(case_ids)
        observed = sum(cid in obs_map for cid in case_ids)
        approved = sum(cid in ref_map for cid in case_ids)
        compared = dcount = agreed = abstains = human_abstains = false_assess = missed = 0
        unsupported_evidence = unsupported_feedback = mismatch = 0
        exclusions: list[tuple[str, str]] = []
        for cid in sorted(case_ids):
            obs = obs_map.get(cid)
            ref = ref_map.get(cid)
            if obs:
                abstains += sum(d.decision == 'ABSTAIN' for d in obs.dimensions)
                # These are descriptive model output flags, not independent judgements.
                unsupported_evidence += sum(d.evidence_quality == 'UNSUPPORTED' for d in obs.dimensions)
                unsupported_feedback += sum(d.feedback_quality == 'UNSUPPORTED' for d in obs.dimensions)
            if not ref or not obs:
                exclusions.append((cid, 'MISSING_APPROVED_REFERENCE' if not ref else 'MISSING_EVALUATOR_OBSERVATION'))
                continue
            compared += 1
            for h, m in zip(ref.dimensions, obs.dimensions):
                dcount += 1
                agreed += h.decision == m.decision
                human_abstains += h.decision == 'ABSTAIN'
                if h.decision != m.decision:
                    mismatch += 1
                    false_assess += h.decision == 'ABSTAIN' and m.decision == 'ASSESS'
                    missed += h.decision == 'ASSESS' and m.decision == 'ABSTAIN'
                elif h.decision == m.decision == 'ASSESS':
                    mismatch += (h.evidence_quality != 'NOT_REVIEWED' and m.evidence_quality != 'NOT_REVIEWED'
                                 and h.evidence_quality != m.evidence_quality)
                    mismatch += (h.feedback_quality != 'NOT_REVIEWED' and m.feedback_quality != 'NOT_REVIEWED'
                                 and h.feedback_quality != m.feedback_quality)
        results.append(FailureSlice(field, value, sub_cases, observed, approved, compared,
                                   dcount, agreed, abstains, human_abstains, false_assess,
                                   missed, unsupported_evidence, unsupported_feedback, mismatch,
                                   tuple(exclusions)))
    # Explicitly avoid drawing relative-group conclusions with synthetic unbalanced cases.
    sufficiently_referenced = sum(s.compared_cases >= min_comparable_cases_for_hypothesis
                                  for s in results if s.field == 'locale')
    hypotheses = ('COLLECT_INDEPENDENT_HUMAN_REFERENCES', 'INCREASE_BALANCED_REGIONAL_COVERAGE',
                  'REVIEW_REGISTER_CONTEXT_AND_VOICE_PROVENANCE')
    if sufficiently_referenced == 0:
        hypotheses += ('INSUFFICIENT_REFERENCES_PER_LOCALE_FOR_COMPARISON',)
    return FailureAnalysisReport(bank.version, tuple(sorted({o.evaluator_version for o in observations})),
                                 len(case_map), len(observations), len(references), tuple(results), hypotheses)
