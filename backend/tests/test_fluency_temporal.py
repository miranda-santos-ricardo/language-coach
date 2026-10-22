import pytest
from app.services.fluency_temporal import (
    SpeechInterval, TemporalEvidenceError, calculate_temporal_metrics,
)


def calc(**override):
    params = dict(locale='fr-CA', recording_duration_ms=4000,
        speech_intervals=[SpeechInterval(500, 1500), SpeechInterval(2000, 3500)],
        evidence_method='validated_speech_vad')
    params.update(override)
    return calculate_temporal_metrics(**params)


@pytest.mark.parametrize('locale', ['fr-CA', 'en-CA', 'en-US', 'en-GB'])
def test_supported_locales(locale):
    result = calc(locale=locale)
    assert result.status == 'MEASURED'
    assert result.locale == locale


def test_duration_and_internal_pauses():
    r = calc()
    assert r.speech_duration_ms == 2500
    assert [(p.start_ms, p.end_ms) for p in r.internal_pause_intervals] == [(1500, 2000)]
    assert r.internal_pause_duration_ms == 500
    assert r.speech_ratio == .625
    assert r.speaking_rate_wpm is None


def test_rates_only_when_transcript_verified():
    r = calc(word_count=10, transcript_verified=True)
    assert r.speaking_rate_wpm == 200.0
    assert r.articulation_rate_wpm == 240.0
    assert r.word_count == 10
    assert calc(word_count=10).speaking_rate_wpm is None


def test_energy_is_not_speech():
    r = calc(evidence_method='energy_activity', word_count=10, transcript_verified=True)
    assert r.status == 'INSUFFICIENT_EVIDENCE'
    assert r.speech_duration_ms is None
    assert r.speaking_rate_wpm is None
    assert r.internal_pause_intervals == ()


def test_no_segments_abstains():
    assert calc(speech_intervals=[]).status == 'INSUFFICIENT_EVIDENCE'
    assert calc(speech_intervals=None, evidence_method='unavailable').status == 'INSUFFICIENT_EVIDENCE'


@pytest.mark.parametrize('intervals', [
    [SpeechInterval(-1, 20)], [SpeechInterval(20, 20)],
    [SpeechInterval(20, 4001)],
    [SpeechInterval(300, 700), SpeechInterval(600, 900)],
    [SpeechInterval(300, 700), SpeechInterval(100, 200)],
    [SpeechInterval(True, 100)],
])
def test_invalid_intervals(intervals):
    with pytest.raises(TemporalEvidenceError):
        calc(speech_intervals=intervals)


@pytest.mark.parametrize('kwargs', [
    {'locale':'fr-FR'}, {'recording_duration_ms':0}, {'recording_duration_ms':60001},
    {'word_count':-1}, {'word_count':True}, {'transcript_verified':True},
    {'minimum_pause_ms':-1}, {'evidence_method':'unexpected'},
])
def test_invalid_inputs(kwargs):
    with pytest.raises(TemporalEvidenceError):
        calc(**kwargs)


def test_threshold_is_inclusive():
    assert len(calc(minimum_pause_ms=500).internal_pause_intervals) == 1
    assert calc(minimum_pause_ms=501).internal_pause_intervals == ()


def test_touching_segments_are_valid():
    r = calc(speech_intervals=[SpeechInterval(100,200), SpeechInterval(200,300)])
    assert r.speech_duration_ms == 200
    assert not r.internal_pause_intervals


def test_no_raw_audio_or_score_in_serialized_result():
    d = calc(word_count=7, transcript_verified=True).to_dict()
    assert 'score' not in d and 'audio' not in d
    assert d['method'] == 'speech-temporal-v0.1'
