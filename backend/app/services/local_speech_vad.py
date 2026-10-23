"""Phase 7 Step 4.2: optional Silero speech VAD, strictly offline.

Requires an installed local silero-vad model (no runtime model download); lazy
imports prevent changes to the default application or test dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
import struct
import time

from app.services.speech_analysis_prototype import (
    SAMPLE_RATE, AudioAnalysisError, _decode_pcm, probe_audio_activity,
)
from app.services.fluency_temporal import SpeechInterval, TemporalMetrics, calculate_temporal_metrics


class VadUnavailable(RuntimeError):
    """Optional local VAD package/model is missing or unusable."""


@dataclass(frozen=True)
class VadComparison:
    locale: str
    speech_segments: tuple[SpeechInterval, ...]
    rms_segments: tuple[SpeechInterval, ...]
    speech_duration_ms: int
    rms_duration_ms: int
    overlap_ms: int
    intersection_over_union: float | None
    elapsed_ms: float
    status: str
    limitations: tuple[str, ...]


def _segments(raw: Any, total_ms: int) -> tuple[SpeechInterval, ...]:
    """Validate and clamp model output; never trust arbitrary model timestamps."""
    if not isinstance(raw, (list, tuple)):
        raise AudioAnalysisError('VAD returned invalid segments')
    segments = []
    last = 0
    for r in raw:
        if not isinstance(r, dict) or not isinstance(r.get('start'), int) or not isinstance(r.get('end'), int):
            raise AudioAnalysisError('VAD returned invalid segment fields')
        start, end = r['start'], r['end']
        if isinstance(start, bool) or isinstance(end, bool) or start < 0 or end <= start or start < last:
            raise AudioAnalysisError('VAD returned invalid or overlapping intervals')
        if start >= total_ms:
            raise AudioAnalysisError('VAD returned segment outside audio')
        # Allow one-sample rounding only, not arbitrary overflow.
        if end > total_ms + 1:
            raise AudioAnalysisError('VAD returned segment outside audio')
        end = min(end, total_ms)
        segments.append(SpeechInterval(start, end))
        last = end
    return tuple(segments)


def _intersection(a: tuple[SpeechInterval,...], b: tuple[SpeechInterval,...]) -> int:
    i = j = overlap = 0
    while i < len(a) and j < len(b):
        x, y = a[i], b[j]
        overlap += max(0, min(x.end_ms, y.end_ms) - max(x.start_ms, y.start_ms))
        if x.end_ms < y.end_ms:
            i += 1
        else:
            j += 1
    return overlap


def _load_silero_model() -> tuple[Any, Callable[...,Any], Any]:
    """Load installed package only; no torch.hub/network downloads."""
    try:
        import torch  # type: ignore
        from silero_vad import load_silero_vad, get_speech_timestamps  # type: ignore
        model = load_silero_vad(onnx=False)
        return model, get_speech_timestamps, torch
    except (ImportError, OSError, RuntimeError) as exc:
        raise VadUnavailable('Install/configure an offline Silero VAD runtime first') from exc


def compare_speech_vad(
    audio: bytes, *, locale: str, consent: bool,
    model_and_fn: tuple[Any, Callable[...,Any], Any] | None = None,
    ffmpeg_binary: str = 'ffmpeg', timeout_seconds: int = 12,
    threshold: float = 0.5,
) -> tuple[VadComparison, TemporalMetrics]:
    """Offline comparison of speech-specific VAD against RMS activity.

    A successful run establishes model execution, NOT detection accuracy or
    learner fluency. `model_and_fn` supports test-only deterministic fakes.
    """
    if not consent:
        raise AudioAnalysisError('Explicit audio assessment consent required')
    if locale not in {'fr-CA', 'en-CA', 'en-US', 'en-GB'}:
        raise AudioAnalysisError('Unsupported locale')
    if not isinstance(audio, bytes):
        raise AudioAnalysisError('Audio must be bytes')
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0.0 < threshold < 1.0:
        raise AudioAnalysisError('Invalid threshold')
    started = time.perf_counter()
    pcm = _decode_pcm(audio, ffmpeg_binary=ffmpeg_binary, timeout_seconds=timeout_seconds)
    total_ms = round((len(pcm) // 2) * 1000 / SAMPLE_RATE)
    if total_ms < 1:
        raise AudioAnalysisError('Audio too short')
    model, fn, torch = model_and_fn if model_and_fn is not None else _load_silero_model()
    try:
        samples = struct.unpack(f'<{len(pcm)//2}h', pcm)
        waveform = torch.tensor([s / 32768.0 for s in samples], dtype=torch.float32)
        raw = fn(waveform, model, sampling_rate=SAMPLE_RATE, threshold=threshold,
                 return_seconds=False)
        # Silero returns sample-index intervals.
        if not isinstance(raw, list):
            raise AudioAnalysisError('Invalid VAD output')
        ms = []
        for r in raw:
            if not isinstance(r, dict) or not isinstance(r.get('start'), int) or not isinstance(r.get('end'), int):
                raise AudioAnalysisError('Invalid VAD output')
            ms.append({'start': round(r['start'] * 1000 / SAMPLE_RATE),
                       'end': round(r['end'] * 1000 / SAMPLE_RATE)})
        speech = _segments(ms, total_ms)
    except AudioAnalysisError:
        raise
    except Exception as exc:
        raise VadUnavailable('Local speech VAD inference failed') from exc
    # Reuse the existing RMS analysis; it is never promoted to speech evidence.
    rms = probe_audio_activity(audio, ffmpeg_binary=ffmpeg_binary,
                               timeout_seconds=timeout_seconds)
    energy = tuple(SpeechInterval(i.start_ms, i.end_ms) for i in rms.active_intervals)
    speech_ms = sum(i.end_ms - i.start_ms for i in speech)
    rms_ms = sum(i.end_ms - i.start_ms for i in energy)
    overlap = _intersection(speech, energy)
    union = speech_ms + rms_ms - overlap
    comparison = VadComparison(
        locale, speech, energy, speech_ms, rms_ms, overlap,
        round(overlap / union, 4) if union else None,
        round((time.perf_counter() - started) * 1000, 2),
        'EXPLORATORY_ONLY',
        ('IoU compares two algorithms, not against ground truth.',
         'VAD identifies probable speech, not pronunciation, language or CEFR.',
         'Timing requires validation with consented annotated speech and noise.',
         'No raw audio or transcripts are stored or transmitted.'),
    )
    temporal = calculate_temporal_metrics(
        locale=locale, recording_duration_ms=total_ms,
        speech_intervals=speech, evidence_method='validated_speech_vad'
    )
    return comparison, temporal
