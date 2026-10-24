import pytest
from dataclasses import replace
from app.services.conversational_evidence import DIMENSIONS
from app.services.conversational_reference_bank import load_reference_case_bank
from app.services.conversational_reliability import (
    DimensionReview, HumanReview, AdjudicatedReference, EvaluatorDimension,
    EvaluatorObservation, ReliabilityContractError, analyze_reliability, text_digest,
)


def fixture_set():
    bank = load_reference_case_bank()
    case = bank.cases[0].calibration
    digest = text_digest(case.text)
    dimensions = tuple(DimensionReview(d, 'ASSESS', 'SUPPORTED', 'SUPPORTED') for d in DIMENSIONS)
    reviewers = tuple(HumanReview(case.case_id, digest, f'reviewer-{i}', 'rubric-v1', dimensions)
                      for i in (1, 2))
    ref = AdjudicatedReference(case.case_id, digest, 'rubric-v1',
                              ('reviewer-1', 'reviewer-2'), 'lead-reviewer', dimensions, True)
    obs = EvaluatorObservation(case.case_id, digest, 'evaluator-v1',
                               tuple(EvaluatorDimension(d, 'ASSESS', 'SUPPORTED', 'SUPPORTED') for d in DIMENSIONS))
    return bank, reviewers, ref, obs


def test_zero_real_human_labels_produces_no_metric():
    bank, _, _, _ = fixture_set()
    report = analyze_reliability(bank, (), (), ())
    assert report.compared_cases == 0
    assert report.decision_agreement_rate is None
    assert report.reviewer_agreement_rate is None
    assert not report.release_ready
    assert len(report.exclusions) == 16


def test_two_independent_reviewers_and_approved_reference():
    bank, reviews, ref, obs = fixture_set()
    report = analyze_reliability(bank, reviews, (ref,), (obs,))
    assert report.compared_cases == 1
    assert report.compared_dimensions == len(DIMENSIONS)
    assert report.decision_agreement_rate == 1
    assert report.evidence_agreement_rate == 1
    assert report.feedback_agreement_rate == 1
    assert report.reviewer_agreement_rate == 1
    assert report.adjudicated_cases == 1
    assert not report.release_ready


def test_model_abstain_is_disagreement_not_semantic_measurement():
    bank, reviews, ref, obs = fixture_set()
    model = list(obs.dimensions)
    model[0] = EvaluatorDimension(DIMENSIONS[0], 'ABSTAIN')
    report = analyze_reliability(bank, reviews, (ref,), (replace(obs, dimensions=tuple(model)),))
    assert report.decision_agreements == len(DIMENSIONS) - 1
    assert report.semantic_evidence_compared == len(DIMENSIONS) - 1
    assert (ref.case_id, DIMENSIONS[0], 'ASSESS_ABSTAIN_DISAGREEMENT') in report.disagreements


def test_semantic_review_distinct_from_text_quote_presence():
    bank, reviews, ref, obs = fixture_set()
    model = list(obs.dimensions)
    model[0] = EvaluatorDimension(DIMENSIONS[0], 'ASSESS', 'UNSUPPORTED', 'UNCERTAIN')
    result = analyze_reliability(bank, reviews, (ref,), (replace(obs, dimensions=tuple(model)),))
    assert result.decision_agreement_rate == 1
    assert result.semantic_evidence_agreements == len(DIMENSIONS) - 1
    assert result.feedback_quality_agreements == len(DIMENSIONS) - 1
    assert len(result.disagreements) == 2


def test_different_text_digest_rejected():
    bank, reviews, ref, obs = fixture_set()
    with pytest.raises(ReliabilityContractError):
        analyze_reliability(bank, reviews, (replace(ref, text_sha256='0' * 64),), (obs,))


def test_adjudication_requires_two_real_independent_reviewers():
    bank, reviews, ref, obs = fixture_set()
    with pytest.raises(ReliabilityContractError):
        analyze_reliability(bank, reviews[:1], (ref,), (obs,))


def test_unapproved_reference_fails_closed():
    bank, reviews, ref, obs = fixture_set()
    with pytest.raises(ReliabilityContractError):
        analyze_reliability(bank, reviews, (replace(ref, approved=False),), (obs,))


def test_duplicate_reviewer_rejected():
    bank, reviews, _, _ = fixture_set()
    with pytest.raises(ReliabilityContractError):
        analyze_reliability(bank, reviews + reviews[:1], (), ())


def test_duplicate_observation_rejected():
    bank, _, _, obs = fixture_set()
    with pytest.raises(ReliabilityContractError):
        analyze_reliability(bank, (), (), (obs, obs))


def test_no_quality_label_for_abstention():
    with pytest.raises(ReliabilityContractError):
        DimensionReview(DIMENSIONS[0], 'ABSTAIN', 'SUPPORTED')


def test_invalid_dimension_order_rejected():
    bank, reviews, ref, obs = fixture_set()
    with pytest.raises(ReliabilityContractError):
        replace(reviews[0], dimensions=tuple(reversed(reviews[0].dimensions)))


def test_reviewers_same_rubric_required_for_adjudication():
    bank, reviews, ref, obs = fixture_set()
    bad = replace(reviews[1], rubric_version='rubric-v2')
    with pytest.raises(ReliabilityContractError):
        analyze_reliability(bank, (reviews[0], bad), (ref,), (obs,))


def test_no_model_calls_or_remote_dependencies():
    bank, _, _, _ = fixture_set()
    result = analyze_reliability(bank, (), (), ())
    assert result.total_cases == 16
    assert result.adjudicated_cases == 0
