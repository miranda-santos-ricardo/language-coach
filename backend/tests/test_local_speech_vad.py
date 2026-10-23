from __future__ import annotations
import math
import struct
import wave
from io import BytesIO
from types import SimpleNamespace
import pytest
from app.services import local_speech_vad as v
from app.services.speech_analysis_prototype import AudioAnalysisError


def wav_data():
    buf = BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(struct.pack('<' + 'h'*16000, *([3000]*16000)))
    return buf.getvalue()


class FakeTorch:
    float32 = 'float32'
    @staticmethod
    def tensor(x, dtype):
        assert len(x) == 16000
        return x


def fake_fn(wave, model, **kw):
    assert kw['return_seconds'] is False
    return [{'start':1600,'end':9600}]


@pytest.fixture
def patched(monkeypatch):
    pcm = struct.pack('<' + 'h'*16000, *([3000]*16000))
    monkeypatch.setattr(v, '_decode_pcm', lambda *a, **k: pcm)
    monkeypatch.setattr(v, 'probe_audio_activity', lambda *a, **k: SimpleNamespace(
        active_intervals=[SimpleNamespace(start_ms=100,end_ms=800)]))
    return (object(), fake_fn, FakeTorch)


@pytest.mark.parametrize('locale', ['fr-CA','en-CA','en-US','en-GB'])
def test_locale(locale, patched):
    res, temporal = v.compare_speech_vad(b'fake', locale=locale, consent=True, model_and_fn=patched)
    assert res.speech_duration_ms == 500
    assert res.overlap_ms == 500
    assert res.intersection_over_union == pytest.approx(0.7143)
    assert res.status == 'EXPLORATORY_ONLY'
    assert temporal.status == 'MEASURED'
    assert temporal.speaking_rate_wpm is None


def test_no_consent(patched):
    with pytest.raises(AudioAnalysisError, match='consent'):
        v.compare_speech_vad(b'fake', locale='fr-CA', consent=False, model_and_fn=patched)


def test_invalid_locale(patched):
    with pytest.raises(AudioAnalysisError, match='locale'):
        v.compare_speech_vad(b'fake', locale='fr-FR', consent=True, model_and_fn=patched)


@pytest.mark.parametrize('threshold', [0,1,-0.2,1.2])
def test_bad_threshold(patched, threshold):
    with pytest.raises(AudioAnalysisError, match='threshold'):
        v.compare_speech_vad(b'fake', locale='fr-CA', consent=True,
                             model_and_fn=patched, threshold=threshold)


def test_non_bytes(patched):
    with pytest.raises(AudioAnalysisError, match='bytes'):
        v.compare_speech_vad('invalid', locale='en-US', consent=True, model_and_fn=patched)


@pytest.mark.parametrize('raw', [None, [{'start':0,'end':0}], [{'start':-1,'end':5}],
                                      [{'start':0,'end':600},{'start':599,'end':900}],
                                      [{'start':950,'end':1002}], [{'start':1000,'end':1200}]])
def test_reject_invalid_segments(raw):
    with pytest.raises(AudioAnalysisError):
        v._segments(raw, 1000)


def test_empty_segments(patched):
    model, _, torch = patched
    res, temporal = v.compare_speech_vad(b'fake', locale='en-CA', consent=True,
                          model_and_fn=(model, lambda *a, **k: [], torch))
    assert temporal.status == 'INSUFFICIENT_EVIDENCE'
    assert res.intersection_over_union == 0


def test_model_failure(patched):
    model, _, torch = patched
    def raise_error(*a, **k):
        raise RuntimeError('model failed')
    with pytest.raises(v.VadUnavailable):
        v.compare_speech_vad(b'fake', locale='en-US', consent=True,
                             model_and_fn=(model, raise_error, torch))


def test_missing_runtime(monkeypatch, patched):
    monkeypatch.setattr(v, '_load_silero_model', lambda: (_ for _ in ()).throw(v.VadUnavailable('missing')))
    with pytest.raises(v.VadUnavailable):
        v.compare_speech_vad(b'fake', locale='en-US', consent=True)


def test_intersection():
    A = (v.SpeechInterval(0,200), v.SpeechInterval(400,600))
    B = (v.SpeechInterval(100,500),)
    assert v._intersection(A,B) == 200


def test_no_torch_import_on_module_import():
    assert callable(v.compare_speech_vad)
