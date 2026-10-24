import json
from copy import deepcopy

import pytest

from app.services.conversational_calibration import CalibrationContractError, run_calibration
from app.services.conversational_evidence import ConversationalAssessmentDraft, DIMENSIONS, DimensionObservation
from app.services.conversational_reference_bank import (
    DEFAULT_BANK_PATH, bank_coverage, load_reference_case_bank, parse_reference_case_bank,
)


def payload():
    return json.loads(DEFAULT_BANK_PATH.read_text(encoding='utf-8'))


def test_load_versioned_cases():
    bank = load_reference_case_bank()
    assert bank.version == '2026-10-23.1'
    assert len(bank.cases) == 16
    assert len(bank.calibration_cases) == 16


def test_coverage_includes_all_locales_and_scenarios():
    summary = bank_coverage(load_reference_case_bank())
    assert summary['required_locale_coverage'] and summary['required_scenario_coverage']
    assert summary['voice_text_unknown_count'] >= 3
    assert summary['short_text_count'] == 2


def test_no_synthetic_cases_claim_human_validation():
    bank = load_reference_case_bank()
    assert bank.reference_status == 'SYNTHETIC_UNREVIEWED'
    assert bank_coverage(bank)['human_reviewed_count'] == 0
    assert all(c.human_reference is None for c in bank.calibration_cases)


def test_filter_by_locale_scenario_tag():
    bank = load_reference_case_bank()
    subset = bank.select(locale='fr-CA', scenario_type='stakeholder_discussion', tag='voice_text_only')
    assert len(subset) == 1
    assert subset[0].calibration.case_id == 'frca-stakeholder-polite-03'


def test_case_bank_compatible_with_existing_harness():
    bank = load_reference_case_bank()
    def deterministic_abstention(case):
        return ConversationalAssessmentDraft('conversational-evidence-v1', case.locale, case.context,
             case.origin, 'INSUFFICIENT_EVIDENCE',
             tuple(DimensionObservation(dim, 'NOT_ASSESSED', 'No model inference', None) for dim in DIMENSIONS),
             ('Synthetic test only',))
    result = run_calibration(bank.calibration_cases, deterministic_abstention)
    assert result.valid_count == 16
    assert result.unreferenced_cases == 16
    assert result.human_agreement_rate is None
    assert result.release_ready is False


@pytest.mark.parametrize('mutation', [
    lambda x: x.update(schema_version='unknown'),
    lambda x: x.update(reference_status='HUMAN_REVIEWED'),
    lambda x: x['cases'][0].update(human_reference=['HUMAN_REVIEWED']*5),
    lambda x: x['cases'][1].update(case_id=x['cases'][0]['case_id']),
    lambda x: x['cases'][0].update(review_focus=['pronunciation']),
    lambda x: x['cases'][0].update(challenge_tags=['unknown']),
    lambda x: x['cases'][0].update(unexpected='value'),
    lambda x: x['cases'][0].update(origin='VOICE_UNVERIFIED'),
    lambda x: x['cases'][0].update(text=''),
    lambda x: x.update(cases=[]),
])
def test_invalid_case_bank_fail_closed(mutation):
    item = deepcopy(payload())
    mutation(item)
    with pytest.raises(CalibrationContractError):
        parse_reference_case_bank(item)


def test_locales_preserve_regional_varieties():
    bank = load_reference_case_bank()
    assert {'fr-CA', 'en-CA', 'en-US', 'en-GB'} == {item.calibration.locale for item in bank.cases}
    assert any('regional_expression' in x.challenge_tags for x in bank.cases)


def test_json_utf8_roundtrip_preserves_accents(tmp_path):
    data = DEFAULT_BANK_PATH.read_text(encoding='utf-8')
    path = tmp_path / 'cases.json'
    path.write_text(data, encoding='utf-8')
    assert 'préoccupation' in load_reference_case_bank(path).cases[2].calibration.text
