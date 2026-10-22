import pytest
from pydantic import ValidationError

from app.services.pronunciation_assessment import (
    LocalEvidenceGateProvider, PronunciationRequest, PronunciationRequestError,
    PronunciationOutcome, PronunciationResult, make_default_pronunciation_provider,
)
from app.schemas.speech_assessment import DimensionStatus


def request(**changes):
    return PronunciationRequest(**({'audio': b'not decoded here', 'locale': 'fr-CA', 'processing_consent': True} | changes))


@pytest.mark.parametrize('locale', ['fr-CA', 'en-CA', 'en-US', 'en-GB'])
def test_supported_locales_abstain(locale):
    result = make_default_pronunciation_provider().assess(request(locale=locale))
    assert result.outcome is PronunciationOutcome.NOT_ASSESSED
    assert result.as_dimension().status is DimensionStatus.NOT_ASSESSED
    assert result.as_dimension().score is None


def test_no_consent_rejected():
    with pytest.raises(PronunciationRequestError, match='consent'):
        LocalEvidenceGateProvider().assess(request(processing_consent=False))


def test_unsupported_locale_rejected():
    with pytest.raises(PronunciationRequestError, match='locale'):
        LocalEvidenceGateProvider().assess(request(locale='fr-FR'))


@pytest.mark.parametrize(
    'audio',
    [b'', 'audio', b'0' * (10 * 1024 * 1024 + 1)],
    ids=['empty', 'invalid_type', 'oversized'],
)
def test_invalid_audio_rejected(audio):
    with pytest.raises(PronunciationRequestError):
        LocalEvidenceGateProvider().assess(request(audio=audio))


def test_invalid_reference_rejected():
    with pytest.raises(PronunciationRequestError, match='reference'):
        LocalEvidenceGateProvider().assess(request(reference_text='  '))


def test_abstention_is_valid_step1_dimension():
    dimension = LocalEvidenceGateProvider().assess(request()).as_dimension()
    assert dimension.evidence_ids == []
    assert dimension.limitations


def test_claimed_assessment_requires_separate_evidence_contract():
    result = PronunciationResult(PronunciationOutcome.ASSESSED, 'test', '1', 'fr-CA', 'claimed', ())
    with pytest.raises(ValueError, match='evidence'):
        result.as_dimension()


def test_no_audio_in_repr_of_result():
    raw = b'private-audio-marker'
    result = LocalEvidenceGateProvider().assess(request(audio=raw))
    assert 'private-audio-marker' not in repr(result)
