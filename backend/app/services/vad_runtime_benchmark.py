"""Phase 7 Step 4.2b offline VAD benchmark; never a fluency/pronunciation score.

Model weights are loaded only on an explicit live run, and can be obtained during
installation; test runs inject their own comparison implementation.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable
import json
import math
import time

from app.services.local_speech_vad import compare_speech_vad

SUPPORTED_LOCALES = frozenset({'fr-CA', 'en-CA', 'en-US', 'en-GB'})
MAX_AUDIO_BYTES = 10 * 1024 * 1024


def _segments(raw: Any, max_duration_ms: int, *, name: str) -> list[tuple[int, int]]:
    if not isinstance(raw, list):
        raise ValueError(f'{name} must be a list')
    output = []
    previous_end = 0
    for item in raw:
        if not isinstance(item, dict) or set(item) != {'start_ms', 'end_ms'}:
            raise ValueError(f'Invalid {name} interval')
        start, end = item['start_ms'], item['end_ms']
        if (type(start) is not int or type(end) is not int or start < previous_end
            or end <= start or end > max_duration_ms):
            raise ValueError(f'Invalid {name} interval bounds')
        output.append((start, end))
        previous_end = end
    return output


def _overlap(left: list[tuple[int, int]], right: list[tuple[int, int]]) -> int:
    i = j = total = 0
    while i < len(left) and j < len(right):
        x, y = left[i], right[j]
        total += max(0, min(x[1], y[1]) - max(x[0], y[0]))
        if x[1] <= y[1]:
            i += 1
        else:
            j += 1
    return total


def evaluate_intervals(predicted: list[dict], annotated: list[dict], duration_ms: int) -> dict:
    """Compare against manual reference, not against an RMS proxy."""
    if type(duration_ms) is not int or duration_ms <= 0:
        raise ValueError('Invalid duration_ms')
    predicted_intervals = _segments(predicted, duration_ms, name='prediction')
    reference_intervals = _segments(annotated, duration_ms, name='reference')
    tp = _overlap(predicted_intervals, reference_intervals)
    predicted_ms = sum(end-start for start,end in predicted_intervals)
    reference_ms = sum(end-start for start,end in reference_intervals)
    fp = predicted_ms-tp
    fn = reference_ms-tp
    union = predicted_ms+reference_ms-tp
    # All-negative examples are not evidence of speech-detection accuracy.
    return {
        'reference_speech_ms': reference_ms,
        'predicted_speech_ms': predicted_ms,
        'overlap_ms': tp,
        'false_positive_ms': fp,
        'false_negative_ms': fn,
        'speech_iou': round(tp / union, 4) if union else None,
        'speech_precision': round(tp / predicted_ms, 4) if predicted_ms else None,
        'speech_recall': round(tp / reference_ms, 4) if reference_ms else None,
        'reference_source': 'MANUAL_ANNOTATION',
        'limitations': ['Frame/boundary rounding affects comparisons.',
                        'Time-weighted scores are not utterance/phoneme accuracy.',
                        'Human annotations require independent quality review.'],
    }


def benchmark_file(
    audio_file: Path, *, locale: str, consent: bool,
    annotation_file: Path | None = None,
    compare: Callable[..., Any] = compare_speech_vad,
) -> dict:
    if not consent:
        raise ValueError('Explicit consent required')
    if locale not in SUPPORTED_LOCALES:
        raise ValueError('Unsupported locale')
    audio_file = Path(audio_file)
    if not audio_file.is_file() or not (0 < audio_file.stat().st_size <= MAX_AUDIO_BYTES):
        raise ValueError('Invalid audio file size')
    audio = audio_file.read_bytes()
    start = time.perf_counter()
    comparison, temporal = compare(audio, locale=locale, consent=True)
    duration_ms = getattr(temporal, 'recording_duration_ms', None)
    if not isinstance(duration_ms, int) or duration_ms <= 0:
        raise ValueError('Invalid temporal duration')
    predicted = [{'start_ms': s.start_ms, 'end_ms': s.end_ms} for s in comparison.speech_segments]
    report = {
        'schema_version': 'vad-benchmark-v1',
        'locale': locale,
        'status': 'EXPLORATORY_ONLY',
        'duration_ms': duration_ms,
        'wall_time_ms': round((time.perf_counter()-start)*1000,2),
        'realtime_factor': round((time.perf_counter()-start)/(duration_ms/1000),4),
        'speech_segments': predicted,
        'rms_silero_iou': comparison.intersection_over_union,
        'reference_comparison': None,
        'limitations': ['No audio bytes or transcript persisted in this report.',
                        'Silero detects likely speech; not pronunciation or fluency.',
                        'RMS agreement is not ground truth.',
                        'Wall time includes model load, decoding and RMS comparison.'],
    }
    if annotation_file is not None:
        annotations = json.loads(Path(annotation_file).read_text(encoding='utf-8'))
        if not isinstance(annotations, dict) or set(annotations) != {'duration_ms','speech_intervals'}:
            raise ValueError('Invalid annotation schema')
        if annotations['duration_ms'] != duration_ms:
            raise ValueError('Annotation duration mismatch')
        report['reference_comparison'] = evaluate_intervals(
            predicted, annotations['speech_intervals'], duration_ms
        )
    return report
