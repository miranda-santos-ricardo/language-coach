"""Phase 7 Step 3.2: offline reference-pair acoustic feasibility, NOT pronunciation grading.

Uses Step 2 decoder to normalize audio. No network, model, storage or user-facing score.
Outputs measurable coarse acoustic descriptors and reference deltas only; these cannot
identify the correctness of any phoneme or accent.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import struct
import time
from typing import Callable

from app.services.speech_analysis_prototype import (
    AudioAnalysisError, SAMPLE_RATE, _decode_pcm,
)
from app.services.pronunciation_assessment import PronunciationRequest, PronunciationRequestError

FRAME_SAMPLES = SAMPLE_RATE // 50  # 20 ms, non-overlapping


@dataclass(frozen=True)
class AcousticDescriptors:
    duration_ms: int
    rms_dbfs: float | None
    zero_crossing_rate: float | None
    activity_ratio: float
    frames: int


@dataclass(frozen=True)
class PronunciationFeasibilityResult:
    method: str
    locale: str
    reference: AcousticDescriptors
    learner: AcousticDescriptors
    duration_difference_ms: int
    activity_ratio_difference: float
    rms_difference_db: float | None
    zero_crossing_rate_difference: float | None
    outcome: str
    elapsed_ms: float
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _describe(pcm: bytes, *, activity_dbfs: float) -> AcousticDescriptors:
    if not pcm or len(pcm) % 2:
        raise AudioAnalysisError('Unusable decoded audio')
    threshold = 10 ** (activity_dbfs / 20)
    squares = 0.0
    crossings = 0
    last_sign = 0
    num_samples = 0
    active_frames = 0
    frame_count = 0
    for start in range(0, len(pcm), FRAME_SAMPLES * 2):
        chunk = pcm[start:start + FRAME_SAMPLES * 2]
        frame_squares = 0.0
        frame_samples = 0
        for (sample,) in struct.iter_unpack('<h', chunk):
            amplitude = sample / 32768.0
            frame_squares += amplitude * amplitude
            sign = 1 if sample > 0 else -1 if sample < 0 else 0
            if sign and last_sign and sign != last_sign:
                crossings += 1
            if sign:
                last_sign = sign
            frame_samples += 1
        squares += frame_squares
        num_samples += frame_samples
        frame_count += 1
        if math.sqrt(frame_squares / frame_samples) >= threshold:
            active_frames += 1
    mean_rms = math.sqrt(squares / num_samples)
    return AcousticDescriptors(
        duration_ms=round(num_samples * 1000 / SAMPLE_RATE),
        rms_dbfs=round(20 * math.log10(mean_rms), 2) if mean_rms > 0 else None,
        zero_crossing_rate=round(crossings / max(1, num_samples - 1), 6),
        activity_ratio=round(active_frames / frame_count, 4),
        frames=frame_count,
    )


def compare_reference_audio(
    request: PronunciationRequest,
    reference_audio: bytes,
    *, ffmpeg_binary: str = 'ffmpeg',
    decode_timeout_seconds: int = 12,
    activity_dbfs: float = -35.0,
    decoder: Callable[..., bytes] = _decode_pcm,
) -> PronunciationFeasibilityResult:
    """Compare coarse *audio* features; cannot assign correctness or fluency.

    Consent must be application-verified for processing both recordings. Caller is
    responsible for verifying consent/rights for the reference recording too.
    The decoder is injected for offline deterministic tests.
    """
    request.validate()
    if not isinstance(reference_audio, bytes) or not 0 < len(reference_audio) <= 10 * 1024 * 1024:
        raise PronunciationRequestError('Invalid reference audio size or type')
    if not math.isfinite(activity_dbfs) or not -90 <= activity_dbfs <= -3:
        raise ValueError('Invalid activity threshold')
    if decode_timeout_seconds <= 0:
        raise ValueError('Invalid decoder timeout')
    start = time.perf_counter()
    ref = _describe(decoder(reference_audio, ffmpeg_binary=ffmpeg_binary,
                            timeout_seconds=decode_timeout_seconds), activity_dbfs=activity_dbfs)
    learner = _describe(decoder(request.audio, ffmpeg_binary=ffmpeg_binary,
                                timeout_seconds=decode_timeout_seconds), activity_dbfs=activity_dbfs)
    rms_delta = (round(learner.rms_dbfs - ref.rms_dbfs, 2)
                 if learner.rms_dbfs is not None and ref.rms_dbfs is not None else None)
    zcr_delta = (round(learner.zero_crossing_rate - ref.zero_crossing_rate, 6)
                 if learner.zero_crossing_rate is not None and ref.zero_crossing_rate is not None else None)
    return PronunciationFeasibilityResult(
        method='coarse-audio-reference-probe-v0.1', locale=request.locale,
        reference=ref, learner=learner,
        duration_difference_ms=learner.duration_ms - ref.duration_ms,
        activity_ratio_difference=round(learner.activity_ratio - ref.activity_ratio, 4),
        rms_difference_db=rms_delta, zero_crossing_rate_difference=zcr_delta,
        outcome='EXPLORATORY_ONLY', elapsed_ms=round((time.perf_counter() - start) * 1000, 2),
        limitations=(
            'No pronunciation accuracy, phoneme correctness, intelligibility or accent score.',
            'Duration, loudness, energy and zero-crossing differences are NOT pronunciation errors.',
            'Reference and learner differences may reflect microphone, gain, noise, speaker or speaking rate.',
            'No time alignment, phoneme labels, validated speech VAD or linguistic comparison.',
            'Raw audio and hashes are not persisted by this module.',
        ),
    )
