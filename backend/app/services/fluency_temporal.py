"""Phase 7 Step 4.1: evidence-gated temporal metrics (offline, no scores).

Consumes *speech* intervals from an independent VAD and optionally a separately
verified lexical word count. Energy-only RMS intervals are explicitly excluded.
No I/O, providers, database writes, CEFR judgments or external calls.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Literal

SUPPORTED = frozenset({'fr-CA', 'en-CA', 'en-US', 'en-GB'})
MAX_MS = 60_000


class TemporalEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class SpeechInterval:
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class TemporalMetrics:
    method: str
    locale: str
    status: Literal['MEASURED', 'INSUFFICIENT_EVIDENCE']
    recording_duration_ms: int
    speech_duration_ms: int | None
    speech_intervals: tuple[SpeechInterval, ...]
    internal_pause_intervals: tuple[SpeechInterval, ...]
    internal_pause_duration_ms: int | None
    speech_ratio: float | None
    speaking_rate_wpm: float | None
    articulation_rate_wpm: float | None
    word_count: int | None
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_temporal_metrics(
    *, locale: str, recording_duration_ms: int,
    speech_intervals: tuple[SpeechInterval, ...] | list[SpeechInterval] | None,
    evidence_method: Literal['validated_speech_vad', 'energy_activity', 'unavailable'],
    word_count: int | None = None,
    transcript_verified: bool = False,
    minimum_pause_ms: int = 200,
) -> TemporalMetrics:
    """Calculate timing only from speech-VAD intervals, not energy activity.

    'validated_speech_vad' means the caller attests that segments are produced by
    a *speech* detector, not that its accuracy is empirically calibrated. Human
    review and VAD calibration remain necessary before pedagogical use.

    WPM is emitted only when `transcript_verified` and `word_count` are supplied
    AND there is valid speech evidence. Does not estimate disfluency or CEFR.
    """
    if locale not in SUPPORTED:
        raise TemporalEvidenceError('Unsupported locale')
    if isinstance(recording_duration_ms, bool) or not isinstance(recording_duration_ms, int) or not 0 < recording_duration_ms <= MAX_MS:
        raise TemporalEvidenceError('Invalid recording duration')
    if isinstance(minimum_pause_ms, bool) or not isinstance(minimum_pause_ms, int) or not 0 <= minimum_pause_ms <= MAX_MS:
        raise TemporalEvidenceError('Invalid minimum pause')
    if word_count is not None and (isinstance(word_count, bool) or not isinstance(word_count, int) or word_count < 0):
        raise TemporalEvidenceError('Invalid word count')
    if transcript_verified and word_count is None:
        raise TemporalEvidenceError('Verified transcript requires word count')
    if evidence_method not in {'validated_speech_vad', 'energy_activity', 'unavailable'}:
        raise TemporalEvidenceError('Unknown evidence method')
    if speech_intervals is not None:
        if not isinstance(speech_intervals, (list, tuple)):
            raise TemporalEvidenceError('Invalid interval collection')
        previous_end = 0
        for index, segment in enumerate(speech_intervals):
            if (not isinstance(segment, SpeechInterval)
                or isinstance(segment.start_ms, bool) or isinstance(segment.end_ms, bool)
                or not isinstance(segment.start_ms, int) or not isinstance(segment.end_ms, int)
                or segment.start_ms < 0 or segment.end_ms <= segment.start_ms
                or segment.end_ms > recording_duration_ms
                or (index > 0 and segment.start_ms < previous_end)):
                raise TemporalEvidenceError('Overlapping, unordered, or invalid speech intervals')
            previous_end = segment.end_ms
    limitations = (
        'Temporal features do not measure pronunciation, intelligibility, CEFR or overall fluency.',
        'VAD segmentation must be calibrated against annotated real speech and noise.',
        'Long pauses may be intentional, rhetorical or context appropriate.',
        'Word count and STT errors affect estimated speaking and articulation rates.',
        'No audio or learner transcripts are persisted by this module.',
    )
    if evidence_method != 'validated_speech_vad' or not speech_intervals:
        return TemporalMetrics('speech-temporal-v0.1', locale, 'INSUFFICIENT_EVIDENCE',
            recording_duration_ms, None, (), (), None, None, None, None,
            word_count if transcript_verified else None,
            limitations + ('No eligible speech-specific segments; energy intervals cannot establish speech.',))
    segments = tuple(speech_intervals)
    speech_ms = sum(s.end_ms - s.start_ms for s in segments)
    pauses = tuple(SpeechInterval(a.end_ms, b.start_ms) for a,b in zip(segments, segments[1:])
                   if b.start_ms - a.end_ms >= minimum_pause_ms)
    span_ms = segments[-1].end_ms - segments[0].start_ms
    words = word_count if transcript_verified else None
    # Speech rate per minute over the span from first to last detected speech,
    # rather than including leading/trailing non-speech recording time.
    speaking = round(words * 60_000 / span_ms, 2) if words is not None and span_ms else None
    articulation = round(words * 60_000 / speech_ms, 2) if words is not None and speech_ms else None
    return TemporalMetrics('speech-temporal-v0.1', locale, 'MEASURED',
        recording_duration_ms, speech_ms, segments, pauses,
        sum(p.end_ms-p.start_ms for p in pauses), round(speech_ms / recording_duration_ms, 4),
        speaking, articulation, words, limitations)
