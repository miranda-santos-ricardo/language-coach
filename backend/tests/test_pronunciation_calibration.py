import copy
import pytest
from app.services.pronunciation_calibration import CalibrationInputError, audit_calibration_manifest


def sample(locale='fr-CA'):
    return {'schema_version': 'calibration-v1', 'recordings': [
        {'id': 'r01', 'locale': locale, 'scenario': 'professional', 'method_version': 'coarse-audio-reference-probe-v0.1', 'capture_condition': 'quiet_room'}],
        'annotations': [
            {'recording_id': 'r01', 'annotator_id': 'judge-a', 'intelligibility': 'intelligible', 'pronunciation_observation': 'no_specific_issue_observed', 'regional_variant_valid': True},
            {'recording_id': 'r01', 'annotator_id': 'judge-b', 'intelligibility': 'intelligible', 'pronunciation_observation': 'no_specific_issue_observed', 'regional_variant_valid': True}]}


@pytest.mark.parametrize('locale', ['fr-CA', 'en-CA', 'en-US', 'en-GB'])
def test_locales_are_covered_without_scores(locale):
    result = audit_calibration_manifest(sample(locale), min_dual_annotated_per_locale=1)
    assert result['by_locale'][locale]['exact_agreement_fraction'] == 1.0
    assert result['status'] == 'HUMAN_ANNOTATION_AUDIT_ONLY'
    assert 'score' not in result


def test_insufficient_coverage_by_default():
    assert audit_calibration_manifest(sample())['by_locale']['fr-CA']['coverage_status'] == 'INSUFFICIENT_EVIDENCE'


def test_disagreement():
    data = sample()
    data['annotations'][1]['intelligibility'] = 'partly_intelligible'
    result = audit_calibration_manifest(data, min_dual_annotated_per_locale=1)
    assert result['by_locale']['fr-CA']['disagreeing_pairs'] == 1
    assert result['by_locale']['fr-CA']['exact_agreement_fraction'] == 0


def test_cannot_judge_excluded():
    data = sample()
    data['annotations'][1]['intelligibility'] = 'cannot_judge'
    result = audit_calibration_manifest(data, min_dual_annotated_per_locale=1)
    assert result['by_locale']['fr-CA']['exact_agreement_fraction'] is None
    assert result['by_locale']['fr-CA']['excluded_cannot_judge_pairs'] == 1
    assert result['by_locale']['fr-CA']['coverage_status'] == 'INSUFFICIENT_EVIDENCE'


def test_unannotated_recording():
    data = sample()
    data['annotations'] = []
    assert audit_calibration_manifest(data)['by_locale']['fr-CA']['dual_annotated_recordings'] == 0


@pytest.mark.parametrize('mutation', [
    lambda x: x['recordings'][0].update(id='bad id'),
    lambda x: x['recordings'][0].update(locale='xx-XX'),
    lambda x: x['recordings'].append(copy.deepcopy(x['recordings'][0])),
    lambda x: x['annotations'].append(copy.deepcopy(x['annotations'][0])),
    lambda x: x['annotations'][0].update(recording_id='not-found'),
    lambda x: x['annotations'][0].update(intelligibility='perfect'),
    lambda x: x['annotations'][0].update(regional_variant_valid='yes'),
    lambda x: x.update(schema_version='v2'),
    lambda x: x['recordings'][0].update(raw_audio='secret'),
    lambda x: x['annotations'][0].update(pronunciation_observation='100'),
], ids=['invalid-id','locale','duplicate-recording','duplicate-rater','orphan','label','regional-type','version','audio-leak-field','invalid-observation'])
def test_invalid_metadata_rejected(mutation):
    data = sample()
    mutation(data)
    with pytest.raises(CalibrationInputError):
        audit_calibration_manifest(data)


def test_does_not_mutate_input():
    data = sample()
    before = copy.deepcopy(data)
    audit_calibration_manifest(data)
    assert data == before


def test_three_raters_are_all_pairwise_compared():
    data = sample()
    third = copy.deepcopy(data['annotations'][0])
    third['annotator_id'] = 'judge-c'
    third['intelligibility'] = 'not_intelligible'
    data['annotations'].append(third)
    r = audit_calibration_manifest(data, min_dual_annotated_per_locale=1)['by_locale']['fr-CA']
    assert r['eligible_annotation_pairs'] == 3
    assert r['agreeing_pairs'] == 1
    assert r['disagreeing_pairs'] == 2
