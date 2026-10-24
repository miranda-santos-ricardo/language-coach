from dataclasses import replace
import pytest

from app.services.conversational_evidence import DIMENSIONS
from app.services.conversational_reference_bank import load_reference_case_bank
from app.services.conversational_reliability import (
    AdjudicatedReference, DimensionReview, EvaluatorDimension,
    EvaluatorObservation, HumanReview, ReliabilityContractError, text_digest,
)
from app.services.conversational_bias_analysis import analyze_bias_and_failures


def bank():
    return load_reference_case_bank()


def evidence(case, model_decision='ASSESS', human_decision='ASSESS'):
    cid = case.calibration.case_id
    digest = text_digest(case.calibration.text)
    h_dims = tuple(DimensionReview(d, human_decision) for d in DIMENSIONS)
    m_dims = tuple(EvaluatorDimension(d, model_decision) for d in DIMENSIONS)
    revs = tuple(HumanReview(cid, digest, f'reviewer-{i}', 'rubric-v1', h_dims) for i in (1, 2))
    ref = AdjudicatedReference(cid, digest, 'rubric-v1', ('reviewer-1', 'reviewer-2'), 'lead', h_dims, True)
    obs = EvaluatorObservation(cid, digest, 'model-v1', m_dims)
    return revs, ref, obs


def get(report, field, val):
    return next(s for s in report.slices if s.field == field and s.value == val)


def test_empty_human_labels_no_fictitious_reliability():
    report = analyze_bias_and_failures(bank())
    assert report.cases == 16 and report.references == 0
    assert all(s.decision_agreement_rate is None for s in report.slices)
    assert not report.release_ready


def test_all_four_locales_exposed():
    r = analyze_bias_and_failures(bank())
    assert {s.value for s in r.slices if s.field == 'locale'} == {'fr-CA', 'en-CA', 'en-US', 'en-GB'}


def test_origin_and_scenario_slices_present():
    r = analyze_bias_and_failures(bank())
    assert any(s.field == 'origin' and s.value == 'VOICE_TEXT_UNKNOWN' for s in r.slices)
    assert {s.value for s in r.slices if s.field == 'scenario_type'} == {
        'executive_update', 'stakeholder_discussion', 'technical_explanation', 'general'}


def test_tags_overlap_and_no_aggregate_double_count():
    r = analyze_bias_and_failures(bank())
    locale_total = sum(s.case_count for s in r.slices if s.field == 'locale')
    tags_total = sum(s.case_count for s in r.slices if s.field == 'challenge_tag')
    assert locale_total == 16 and tags_total > 16


def test_observations_without_humans_are_not_reliability_metrics():
    b = bank()
    _, _, obs = evidence(b.cases[0])
    r = analyze_bias_and_failures(b, observations=(obs,))
    s = get(r, 'locale', b.cases[0].calibration.locale)
    assert s.observed_cases >= 1 and s.decision_agreement_rate is None


def test_model_abstention_rate_only_when_observed():
    b = bank()
    _, _, obs = evidence(b.cases[0], 'ABSTAIN')
    r = analyze_bias_and_failures(b, observations=(obs,))
    s = get(r, 'locale', b.cases[0].calibration.locale)
    assert s.observed_abstention_rate == 1
    assert get(r, 'locale', 'en-GB').observed_abstention_rate is None or b.cases[0].calibration.locale == 'en-GB'


def test_false_assessment_against_approved_human_abstain():
    b = bank()
    revs, ref, obs = evidence(b.cases[0], 'ASSESS', 'ABSTAIN')
    r = analyze_bias_and_failures(b, revs, (ref,), (obs,))
    s = get(r, 'locale', b.cases[0].calibration.locale)
    assert s.false_assessments == 5 and s.missed_assessments == 0 and s.decision_agreement_rate == 0


def test_missed_assessment_against_approved_human_assess():
    b = bank()
    revs, ref, obs = evidence(b.cases[0], 'ABSTAIN', 'ASSESS')
    r = analyze_bias_and_failures(b, revs, (ref,), (obs,))
    s = get(r, 'locale', b.cases[0].calibration.locale)
    assert s.missed_assessments == 5


def test_equal_decisions_reference_grounded():
    b = bank()
    revs, ref, obs = evidence(b.cases[0])
    r = analyze_bias_and_failures(b, revs, (ref,), (obs,))
    s = get(r, 'locale', b.cases[0].calibration.locale)
    assert s.compared_cases == 1 and s.decision_agreement_rate == 1
    assert not r.release_ready


def test_invalid_source_digest_rejected():
    b = bank()
    revs, ref, obs = evidence(b.cases[0])
    with pytest.raises(ReliabilityContractError):
        analyze_bias_and_failures(b, revs, (ref,), (replace(obs, text_sha256='0' * 64),))


def test_unapproved_human_label_rejected():
    b = bank()
    revs, ref, obs = evidence(b.cases[0])
    with pytest.raises(ReliabilityContractError):
        analyze_bias_and_failures(b, revs, (replace(ref, approved=False),), (obs,))


def test_no_statistical_bias_conclusion_or_cefr_claim():
    r = analyze_bias_and_failures(bank())
    assert r.methodology == 'DESCRIPTIVE_SYNTHETIC_NOT_BIAS_PROOF'
    assert 'COLLECT_INDEPENDENT_HUMAN_REFERENCES' in r.gap_hypotheses
    assert not hasattr(r, 'cefr_accuracy')


def test_invalid_threshold_rejected():
    with pytest.raises(ReliabilityContractError):
        analyze_bias_and_failures(bank(), min_comparable_cases_for_hypothesis=1)
