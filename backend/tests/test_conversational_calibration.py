from dataclasses import replace
import pytest
from app.services.conversational_calibration import (
    CalibrationCase, CalibrationContractError, audit_case, run_calibration,
)
from app.services.conversational_evidence import (
    ConversationalAssessmentDraft, DIMENSIONS, DimensionObservation,
)


def case(**kwargs):
    return CalibrationCase('fr-01', 'fr-CA', 'professional', 'executive_update',
                           'Je recommande une décision progressive.', 'VOICE_TEXT_UNKNOWN', **kwargs)


def draft(c, *, assessed=False):
    return ConversationalAssessmentDraft(
        'conversational-evidence-v1', c.locale, c.context, c.origin,
        'REVIEWED' if assessed else 'INSUFFICIENT_EVIDENCE',
        tuple(DimensionObservation(d, 'MODEL_JUDGMENT' if assessed else 'NOT_ASSESSED',
            'Explanation', c.text[:12] if assessed else None) for d in DIMENSIONS),
        ('Text-only review',))


def test_voice_unknown_text_only_is_valid():
    c=case()
    assert audit_case(c,draft(c,assessed=True)).contract_valid


def test_unverified_quote_is_flagged():
    c=case()
    d=draft(c,assessed=True)
    obs=list(d.dimensions)
    obs[0]=replace(obs[0],supporting_quote='fabricated citation')
    result=audit_case(c,replace(d,dimensions=tuple(obs)))
    assert not result.contract_valid
    assert 'UNSUPPORTED_QUOTE' in result.errors


def test_typed_origin_mismatch():
    c=case()
    assert 'CASE_METADATA_MISMATCH' in audit_case(c,replace(draft(c),text_origin='TYPED')).errors


def test_short_text_abstention_rule():
    c=replace(case(),text='Bonjour!')
    assert 'ASSESSED_INSUFFICIENT_TEXT' in audit_case(c,draft(c,assessed=True)).errors


def test_unreviewed_cannot_claim_observation():
    c=case()
    assert 'UNREVIEWED_WITH_ASSESSMENT' in audit_case(c,replace(draft(c,assessed=True),status='AWAITING_EVALUATOR')).errors


def test_missing_human_references_are_not_assumed():
    c=case()
    report=run_calibration((c,),lambda _: draft(c))
    assert report.human_agreement_rate is None
    assert report.unreferenced_cases == 1
    assert report.release_ready is False


def test_human_agreement_is_on_abstention_not_semantic_accuracy():
    c=case(human_reference=('HUMAN_REVIEWED',)*5)
    report=run_calibration((c,),lambda _: draft(c,assessed=True))
    assert report.human_comparable == 5
    assert report.human_agreement_rate == 1.0
    assert not report.release_ready


def test_disagreement_on_assessed_vs_abstained():
    c=case(human_reference=('HUMAN_REVIEWED',)*5)
    report=run_calibration((c,),lambda _: draft(c))
    assert report.human_agreement_rate == 0.0


def test_duplicate_id_rejected():
    c=case()
    with pytest.raises(CalibrationContractError):
        run_calibration((c,c),lambda _: draft(c))


def test_assessor_failure_is_reported_without_leaking_exception():
    c=case()
    def fail(_): raise RuntimeError('secret provider text')
    report=run_calibration((c,),fail)
    assert report.invalid_count == 1
    assert report.audits[0].errors == ('ASSESSOR_FAILED',)
    assert 'secret' not in str(report)


def test_reference_shape_rejected():
    with pytest.raises(CalibrationContractError):
        case(human_reference=('HUMAN_REVIEWED',))


def test_separate_locale_cases():
    a=case()
    b=replace(a,case_id='en-01',locale='en-CA',text='I recommend a gradual approach.',origin='TYPED')
    report=run_calibration((a,b),lambda c:draft(c))
    assert report.valid_count == 2
    assert report.abstention_rate == 1.0
