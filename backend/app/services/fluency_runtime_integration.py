"""Phase 7 Step 4.3: consent-gated offline speech timing integration.

This is an internal integration boundary, NOT an HTTP endpoint or a calibrated
fluency/pronunciation assessment. No audio, transcript or identity is persisted.
Caller must enforce authenticated ownership and bind consent to the recording.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from app.services.fluency_temporal import (
    SUPPORTED, SpeechInterval, TemporalMetrics, calculate_temporal_metrics,
)
from app.services.local_speech_vad import VadComparison, compare_speech_vad


class FluencyIntegrationError(ValueError):
    """Rejected untrusted metadata at the integration boundary."""


@dataclass(frozen=True)
class FluencyObservation:
    schema_version: str
    status: str
    locale: str
    detector: str
    timing: TemporalMetrics
    rms_silero_iou: float | None
    detector_wall_time_ms: float
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def observe_fluency_timing(
    audio: bytes, *, locale: str, consent: bool,
    verified_word_count: int | None = None,
    transcript_verified: bool = False,
    minimum_pause_ms: int = 200,
    vad: Callable[..., tuple[VadComparison, TemporalMetrics]] = compare_speech_vad,
) -> FluencyObservation:
    """Measure VAD-dependent timing without making pedagogical judgments.

    `transcript_verified` must mean that word count was independently checked
    against this exact recording; the caller must ensure that binding. A mere
    STT result or an edited draft is NOT proof of transcript verification.
    """
    if consent is not True:
        raise FluencyIntegrationError('Explicit recording-specific consent required')
    if locale not in SUPPORTED:
        raise FluencyIntegrationError('Unsupported locale')
    if not isinstance(audio, bytes) or not audio:
        raise FluencyIntegrationError('Audio must be nonempty bytes')
    if type(transcript_verified) is not bool:
        raise FluencyIntegrationError('Invalid transcript verification flag')
    if verified_word_count is not None and (type(verified_word_count) is not int or verified_word_count < 0):
        raise FluencyIntegrationError('Invalid verified word count')
    if transcript_verified and verified_word_count is None:
        raise FluencyIntegrationError('Transcript verification requires word count')
    if not transcript_verified and verified_word_count is not None:
        raise FluencyIntegrationError('Word count supplied without verification')
    if type(minimum_pause_ms) is not int or not 0 <= minimum_pause_ms <= 60000:
        raise FluencyIntegrationError('Invalid pause threshold')

    comparison, initial = vad(audio, locale=locale, consent=True)
    if not isinstance(comparison, VadComparison) or not isinstance(initial, TemporalMetrics):
        raise FluencyIntegrationError('Invalid detector response')
    if comparison.locale != locale or initial.locale != locale:
        raise FluencyIntegrationError('Detector locale mismatch')
    if comparison.status != 'EXPLORATORY_ONLY' or initial.method != 'speech-temporal-v0.1':
        raise FluencyIntegrationError('Unknown detector evidence')
    if initial.status not in ('MEASURED', 'INSUFFICIENT_EVIDENCE'):
        raise FluencyIntegrationError('Invalid detector status')
    if tuple(comparison.speech_segments) != tuple(initial.speech_intervals):
        raise FluencyIntegrationError('Detector/metrics segment mismatch')
    if type(initial.recording_duration_ms) is not int or initial.recording_duration_ms <= 0:
        raise FluencyIntegrationError('Invalid decoded audio duration')
    if type(comparison.elapsed_ms) not in (int, float) or not 0 <= comparison.elapsed_ms < float('inf'):
        raise FluencyIntegrationError('Invalid detector execution time')
    if comparison.intersection_over_union is not None and (
        type(comparison.intersection_over_union) not in (float, int)
        or not 0 <= comparison.intersection_over_union <= 1
    ):
        raise FluencyIntegrationError('Invalid algorithm agreement')

    # Recompute from VAD-specific intervals; don't reuse RMS intervals as speech.
    # A nonempty prediction is algorithmic evidence, not human-calibrated truth.
    timing = calculate_temporal_metrics(
        locale=locale,
        recording_duration_ms=initial.recording_duration_ms,
        speech_intervals=comparison.speech_segments,
        evidence_method='validated_speech_vad',
        word_count=verified_word_count,
        transcript_verified=transcript_verified,
        minimum_pause_ms=minimum_pause_ms,
    )
    return FluencyObservation(
        schema_version='fluency-observation-v1', status='EXPLORATORY_ONLY',
        locale=locale, detector='silero-vad-local', timing=timing,
        rms_silero_iou=comparison.intersection_over_union,
        detector_wall_time_ms=float(comparison.elapsed_ms),
        limitations=(
            'Silero speech boundaries are uncalibrated against independent human reference.',
            'Observed pauses are not necessarily hesitations or fluency defects.',
            'Speaking and articulation rates require independently verified word counts.',
            'RMS agreement is not model accuracy or a proficiency score.',
            'No raw audio, transcript, user identifiers or model score are stored by this service.',
            'Consent and authenticated recording ownership must be enforced by the caller.',
        ),
    )
