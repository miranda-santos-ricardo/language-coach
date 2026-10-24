import pytest
from dataclasses import FrozenInstanceError

from app.services.conversational_reference_bank import load_reference_case_bank, ReferenceCaseBank
from app.services.conversational_quality_closure import (
    close_conversational_quality, EXTERNAL_RELEASE_GATES, QualityClosureReport,
)
from app.services.conversational_reliability import ReliabilityContractError


@pytest.fixture
def report():
    return close_conversational_quality(load_reference_case_bank())


def test_reference_bank_coverage_is_reported(report):
    assert report.case_count == 16
    assert report.bank_version
    assert report.slice_count > 0


def test_no_human_data_is_not_measured_agreement(report):
    assert report.decision_agreement_rate is None
    assert report.evidence_agreement_rate is None
    assert report.feedback_agreement_rate is None


def test_no_references_are_not_misrepresented_as_reviewed(report):
    assert report.reviewed_cases == report.adjudicated_cases == report.compared_cases == 0


def test_missing_evidence_is_enumerated(report):
    assert 'INDEPENDENT_HUMAN_REVIEW' in report.unmet_evidence
    assert 'SEMANTIC_EVIDENCE_REVIEW' in report.unmet_evidence
    assert 'FEEDBACK_QUALITY_REVIEW' in report.unmet_evidence


def test_report_never_authorizes_release(report):
    assert report.release_ready is False
    assert report.decision == 'NOT_VALIDATED_FOR_RELEASE'


def test_external_security_gates_are_explicit(report):
    assert report.external_release_gates == EXTERNAL_RELEASE_GATES
    assert 'POSTGRESQL_CONCURRENCY_VALIDATED' in report.external_release_gates


def test_json_safe_summary(report):
    import json
    payload = report.as_dict()
    assert json.loads(json.dumps(payload))['release_ready'] is False
    assert payload['unmet_evidence']


def test_immutable_report(report):
    with pytest.raises(FrozenInstanceError):
        report.decision = 'GO'


def test_invalid_bank_fails_closed():
    with pytest.raises(ReliabilityContractError):
        close_conversational_quality(object())


def test_bad_observation_tuple_fails_closed():
    with pytest.raises(ReliabilityContractError):
        close_conversational_quality(load_reference_case_bank(), observations=['not-an-observation'])
