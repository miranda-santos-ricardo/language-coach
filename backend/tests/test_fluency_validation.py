from __future__ import annotations

import json
import pytest

from app.services.fluency_temporal import SpeechInterval, calculate_temporal_metrics
from app.services.local_speech_vad import VadComparison
from app.services.fluency_validation import validate_fluency_pipeline, FluencyValidationError
from app.services.fluency_validation_cli import main


def fake_vad(audio, *, locale, consent):
    assert consent is True and audio == b'not-real-audio'
    segments = (SpeechInterval(500, 1600), SpeechInterval(1900, 2800))
    timing = calculate_temporal_metrics(locale=locale, recording_duration_ms=3500,
                                        speech_intervals=segments, evidence_method='validated_speech_vad')
    comparison = VadComparison(locale, segments, (), 2000, 0, 0, 0.5, 33.0, 'EXPLORATORY_ONLY', ())
    return comparison, timing


def fake_silence(audio, *, locale, consent):
    timing = calculate_temporal_metrics(locale=locale, recording_duration_ms=3000,
                                        speech_intervals=(), evidence_method='validated_speech_vad')
    return VadComparison(locale, (), (), 0, 0, 0, None, 12.0, 'EXPLORATORY_ONLY', ()), timing


@pytest.mark.parametrize('locale', ['fr-CA', 'en-CA', 'en-US', 'en-GB'])
@pytest.mark.parametrize('context', ['professional', 'conversational'])
def test_pipeline_locales_contexts(locale, context):
    result = validate_fluency_pipeline(b'not-real-audio', locale=locale, context=context,
                                       consent=True, vad=fake_vad)
    assert result.status == 'EXPLORATORY_ONLY'
    assert result.feedback.status == 'OBSERVATIONAL_ONLY'
    assert result.observation.timing.speech_duration_ms == 2000
    assert len(result.observation.timing.internal_pause_intervals) == 1
    assert result.observation.timing.speaking_rate_wpm is None
    assert 'score' not in result.to_dict()
    assert result.to_dict()['feedback']['items']


@pytest.mark.parametrize('locale', ['fr-CA', 'en-CA', 'en-US', 'en-GB'])
def test_silence_abstains(locale):
    report = validate_fluency_pipeline(b'not-real-audio', locale=locale, context='conversational',
                                      consent=True, vad=fake_silence)
    assert report.status == 'INSUFFICIENT_EVIDENCE'
    assert report.feedback.status == 'INSUFFICIENT_EVIDENCE'
    assert all(item.kind == 'limitation' for item in report.feedback.items)


def test_consent_before_vad():
    def forbidden(*a, **kw):
        pytest.fail('VAD must not be called')
    with pytest.raises(FluencyValidationError, match='consent'):
        validate_fluency_pipeline(b'not-real-audio', locale='fr-CA', context='professional',
                                  consent=False, vad=forbidden)


@pytest.mark.parametrize('context', ['bad', '', None])
def test_invalid_context(context):
    with pytest.raises(FluencyValidationError, match='context'):
        validate_fluency_pipeline(b'not-real-audio', locale='fr-CA', context=context,
                                  consent=True, vad=fake_vad)


@pytest.mark.parametrize('pause', [-1, True, 60001, '200'])
def test_invalid_pause(pause):
    with pytest.raises(FluencyValidationError, match='pause'):
        validate_fluency_pipeline(b'not-real-audio', locale='fr-CA', context='professional',
                                  consent=True, minimum_pause_ms=pause, vad=fake_vad)


@pytest.mark.parametrize('audio', [b'', 'fake', None, bytearray(b'a')])
def test_invalid_audio(audio):
    with pytest.raises(FluencyValidationError, match='Audio'):
        validate_fluency_pipeline(audio, locale='fr-CA', context='professional',
                                  consent=True, vad=fake_vad)


def test_bad_locale():
    with pytest.raises(ValueError, match='locale'):
        validate_fluency_pipeline(b'not-real-audio', locale='pt-BR', context='professional',
                                  consent=True, vad=fake_vad)


def test_cli_rejects_no_consent(capsys):
    assert main(['--audio', 'missing.mp4', '--locale', 'fr-CA']) == 1
    assert json.loads(capsys.readouterr().err)['status'] == 'FAILED'


def test_cli_rejects_missing_audio(capsys):
    assert main(['--audio', 'missing.mp4', '--locale', 'fr-CA', '--consent']) == 1
    assert 'FAILED' in capsys.readouterr().err


def test_cli_valid_json(monkeypatch, tmp_path, capsys):
    path = tmp_path / 'audio.mp4'
    path.write_bytes(b'not-real-audio')
    import app.services.fluency_validation_cli as cli
    monkeypatch.setattr(cli, 'validate_fluency_pipeline', lambda audio, **kw:
        validate_fluency_pipeline(audio, vad=fake_vad, **kw))
    assert main(['--audio', str(path), '--locale', 'fr-CA', '--context', 'professional', '--consent']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['schema_version'] == 'fluency-validation-v1'
    assert result['feedback']['status'] == 'OBSERVATIONAL_ONLY'
    assert result['observation']['timing']['word_count'] is None


def test_cli_size_limit(monkeypatch, tmp_path, capsys):
    path = tmp_path / 'large.mp4'
    with path.open('wb') as stream:
        stream.truncate(10 * 1024 * 1024 + 1)
    assert main(['--audio', str(path), '--locale', 'fr-CA', '--consent']) == 1
    assert 'FAILED' in capsys.readouterr().err
