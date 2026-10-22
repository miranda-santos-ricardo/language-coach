"""Offline Step 2 verification with generated waveforms; no private voices or APIs."""
import io
import math
import shutil
import struct
import wave

import pytest

from app.services.speech_analysis_prototype import AudioAnalysisError, probe_audio_activity


def wav_data(pieces, rate=16000):
    samples = []
    for seconds, amplitude in pieces:
        for n in range(round(rate * seconds)):
            samples.append(round(32767 * amplitude * math.sin(2 * math.pi * 440 * n / rate)))
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(struct.pack('<' + 'h' * len(samples), *samples))
    return stream.getvalue()


pytestmark = pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='local ffmpeg not installed')


def test_duration_and_activity_intervals():
    data = wav_data([(0.2, 0), (0.4, 0.4), (0.3, 0), (0.4, 0.4), (0.2, 0)])
    result = probe_audio_activity(data)
    assert result.duration_ms == 1500
    assert result.status == 'ACTIVITY_DETECTED'
    assert len(result.active_intervals) == 2
    assert len(result.internal_inactive_intervals) == 1
    gap = result.internal_inactive_intervals[0]
    assert 260 <= gap.end_ms - gap.start_ms <= 340
    assert result.active_duration_ms > 700


def test_silence_is_not_pronunciation_failure():
    result = probe_audio_activity(wav_data([(0.5, 0)]))
    assert result.status == 'NO_ACTIVITY_DETECTED'
    assert not result.active_intervals
    assert result.internal_inactive_duration_ms == 0
    assert 'phonemes' in ' '.join(result.limitations)


def test_quiet_sound_below_threshold():
    result = probe_audio_activity(wav_data([(0.5, 0.001)]))
    assert result.status == 'NO_ACTIVITY_DETECTED'


def test_malformed_audio_rejected():
    with pytest.raises(AudioAnalysisError):
        probe_audio_activity(b'not audio')


def test_empty_and_oversized_rejected():
    for data in (b'', b'x' * (10 * 1024 * 1024 + 1)):
        with pytest.raises(AudioAnalysisError):
            probe_audio_activity(data)


def test_invalid_settings_rejected():
    audio = wav_data([(0.2, 0.2)])
    with pytest.raises(AudioAnalysisError):
        probe_audio_activity(audio, threshold_dbfs=float('nan'))
    with pytest.raises(AudioAnalysisError):
        probe_audio_activity(audio, min_active_ms=0)


def test_deterministic_repeat():
    audio = wav_data([(0.3, 0.2), (0.2, 0), (0.3, 0.2)])
    assert probe_audio_activity(audio).to_dict() == probe_audio_activity(audio).to_dict()


def test_missing_decoder_rejected():
    with pytest.raises(AudioAnalysisError, match='unavailable'):
        probe_audio_activity(wav_data([(0.2, 0.2)]), ffmpeg_binary='does-not-exist-ffmpeg')


def test_no_false_speech_claim():
    # A sine wave triggers energy: proves this detector must NOT be called speech VAD.
    result = probe_audio_activity(wav_data([(0.3, 0.4)]))
    assert result.status == 'ACTIVITY_DETECTED'
    assert result.method == 'energy-rms-v0.1'
    assert any('not validated speech' in x for x in result.limitations)
