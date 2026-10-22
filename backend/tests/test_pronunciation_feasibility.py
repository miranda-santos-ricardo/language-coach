"""Offline deterministic Step 3.2 experiments. No external provider or downloads."""
import math
import struct
import pytest

from app.services.pronunciation_assessment import PronunciationRequest, PronunciationRequestError
from app.services.pronunciation_feasibility import compare_reference_audio
from app.services.speech_analysis_prototype import AudioAnalysisError


def make_pcm(freq=220, seconds=.2, amplitude=.35):
    n = round(16000 * seconds)
    samples = [round(32767 * amplitude * math.sin(2 * math.pi * freq * t / 16000)) for t in range(n)]
    return struct.pack('<' + 'h' * n, *samples)


def req(audio=b'learner', locale='fr-CA', consent=True):
    return PronunciationRequest(audio=audio, locale=locale, processing_consent=consent,
                                reference_text='Bonjour')


def decoder(data, **kwargs):
    if data == b'reference':
        return make_pcm()
    if data == b'learner':
        return make_pcm(freq=260, seconds=.25)
    if data == b'silence':
        return b'\0\0' * 3200
    raise AudioAnalysisError('Unsupported test fixture')


@pytest.mark.parametrize('locale', ['fr-CA', 'en-CA', 'en-US', 'en-GB'])
def test_locales_supported_without_scoring(locale):
    result = compare_reference_audio(req(locale=locale), b'reference', decoder=decoder)
    assert result.outcome == 'EXPLORATORY_ONLY'
    assert not hasattr(result, 'pronunciation_score')
    assert result.learner.duration_ms == 250
    assert result.duration_difference_ms == 50
    assert result.locale == locale
    assert 'limitations' in result.to_dict()


def test_difference_never_claims_error():
    result = compare_reference_audio(req(), b'reference', decoder=decoder)
    assert result.rms_difference_db is not None
    assert result.zero_crossing_rate_difference is not None
    assert 'NOT pronunciation errors' in ' '.join(result.limitations)


def test_silence_is_measured_without_speech_claim():
    result = compare_reference_audio(req(audio=b'silence'), b'reference', decoder=decoder)
    assert result.learner.rms_dbfs is None
    assert result.learner.activity_ratio == 0
    assert result.rms_difference_db is None


def test_no_consent_blocks_decoder():
    called = []
    def forbidden(*args, **kwargs):
        called.append(True)
        raise AssertionError('Should not decode')
    with pytest.raises(PronunciationRequestError):
        compare_reference_audio(req(consent=False), b'reference', decoder=forbidden)
    assert not called


@pytest.mark.parametrize('bad', [b'', 'string', b'x' * (10 * 1024 * 1024 + 1)], ids=['empty','not_bytes','oversize'])
def test_reference_validation(bad):
    with pytest.raises(PronunciationRequestError):
        compare_reference_audio(req(), bad, decoder=decoder)


def test_decoder_failure_is_controlled():
    with pytest.raises(AudioAnalysisError):
        compare_reference_audio(req(), b'unsupported', decoder=decoder)


@pytest.mark.parametrize('level', [float('nan'), -100.0, 0.0], ids=['nan','low','high'])
def test_invalid_threshold(level):
    with pytest.raises(ValueError):
        compare_reference_audio(req(), b'reference', activity_dbfs=level, decoder=decoder)


def test_no_provider_calls_or_storage(tmp_path):
    assert list(tmp_path.iterdir()) == []
    compare_reference_audio(req(), b'reference', decoder=decoder)
    assert list(tmp_path.iterdir()) == []
