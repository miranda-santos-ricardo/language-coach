from dataclasses import replace
from dataclasses import asdict
import pytest
from app.services.fluency_temporal import SpeechInterval, calculate_temporal_metrics
from app.services.local_speech_vad import VadComparison
from app.services.fluency_runtime_integration import (
    FluencyIntegrationError, observe_fluency_timing,
)


def evidence(locale='fr-CA', intervals=(SpeechInterval(1000, 3000), SpeechInterval(3500, 5000))):
    comparison = VadComparison(locale, intervals, (), 3500, 0, 0, 0.75, 12.5,
                               'EXPLORATORY_ONLY', ())
    timing = calculate_temporal_metrics(locale=locale, recording_duration_ms=6000,
              speech_intervals=intervals, evidence_method='validated_speech_vad')
    return comparison, timing


def fake_vad(locale='fr-CA', intervals=None):
    calls = []
    def fn(audio, *, locale, consent):
        calls.append((audio, locale, consent))
        c, t = evidence(locale)
        if intervals is not None:
            c,t = evidence(locale, intervals)
        return c,t
    return fn, calls


@pytest.mark.parametrize('locale', ['fr-CA','en-CA','en-US','en-GB'])
def test_locale_and_observations(locale):
    f, calls = fake_vad()
    r = observe_fluency_timing(b'audio', locale=locale, consent=True, vad=f)
    assert len(calls) == 1
    assert calls[0] == (b'audio', locale, True)
    assert r.status == 'EXPLORATORY_ONLY'
    assert r.timing.status == 'MEASURED'
    assert r.timing.speech_duration_ms == 3500
    assert r.timing.internal_pause_duration_ms == 500
    assert r.timing.speech_ratio == pytest.approx(0.5833)
    assert r.timing.speaking_rate_wpm is None
    assert r.rms_silero_iou == 0.75


def test_verified_words_enable_rates():
    f,_ = fake_vad()
    r = observe_fluency_timing(b'a', locale='fr-CA', consent=True, vad=f,
                               verified_word_count=10, transcript_verified=True)
    assert r.timing.speaking_rate_wpm == 150.0
    assert r.timing.articulation_rate_wpm == pytest.approx(171.43)


def test_custom_pause_threshold():
    f,_ = fake_vad()
    r = observe_fluency_timing(b'a', locale='fr-CA', consent=True, vad=f, minimum_pause_ms=501)
    assert r.timing.internal_pause_intervals == ()
    assert r.timing.internal_pause_duration_ms == 0


def test_no_speech_abstains():
    f,_ = fake_vad(intervals=())
    r = observe_fluency_timing(b'a', locale='en-US', consent=True, vad=f)
    assert r.timing.status == 'INSUFFICIENT_EVIDENCE'
    assert r.timing.speaking_rate_wpm is None
    assert r.timing.speech_duration_ms is None


@pytest.mark.parametrize('kwargs', [
    {'consent':False}, {'consent':1}, {'locale':'fr-FR'}, {'audio':b''},
    {'audio':'str'}, {'transcript_verified':True},
    {'verified_word_count':2}, {'verified_word_count':-1, 'transcript_verified':True},
    {'verified_word_count':True, 'transcript_verified':True},
    {'transcript_verified':'yes'}, {'minimum_pause_ms':-1}, {'minimum_pause_ms':True},
])
def test_bad_inputs_prevent_detector_call(kwargs):
    f,calls = fake_vad()
    args = dict(audio=b'a', locale='en-US', consent=True, vad=f)
    args.update(kwargs)
    with pytest.raises(FluencyIntegrationError):
        observe_fluency_timing(**args)
    assert calls == []


@pytest.mark.parametrize('modifier', [
    lambda c,t:(replace(c,locale='en-US'),t),
    lambda c,t:(c,replace(t,locale='en-US')),
    lambda c,t:(replace(c,status='MEASURED'),t),
    lambda c,t:(c,replace(t,method='unknown')),
    lambda c,t:(replace(c,speech_segments=()),t),
    lambda c,t:(replace(c,elapsed_ms=-1),t),
    lambda c,t:(replace(c,intersection_over_union=2.0),t),
    lambda c,t:(c,replace(t,recording_duration_ms=0)),
])
def test_invalid_detector_evidence_rejected(modifier):
    c,t = modifier(*evidence())
    with pytest.raises(FluencyIntegrationError):
        observe_fluency_timing(b'a',locale='fr-CA',consent=True,vad=lambda *a,**k:(c,t))


def test_detector_error_propagates_without_forged_metrics():
    def fail(*args,**kwargs):
        raise RuntimeError('unavailable')
    with pytest.raises(RuntimeError):
        observe_fluency_timing(b'a',locale='fr-CA',consent=True,vad=fail)


def test_no_raw_audio_or_scores_in_report():
    f,_=fake_vad()
    out=observe_fluency_timing(b'secret',locale='fr-CA',consent=True,vad=f).to_dict()
    s=str(out)
    assert 'secret' not in s
    assert 'audio' not in out and 'transcript' not in out and 'score' not in out
    assert out['limitations']
