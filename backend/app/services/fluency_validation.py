"""Phase 7 Step 4.5: local, consent-gated fluency pipeline validation.

Not a production API, an accuracy benchmark, or a proficiency assessment.
No raw audio, transcripts or identity are written by this service.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Literal

from app.services.fluency_feedback import FluencyFeedback, build_fluency_feedback
from app.services.fluency_runtime_integration import FluencyObservation, observe_fluency_timing


class FluencyValidationError(ValueError):
    pass


@dataclass(frozen=True)
class FluencyValidationReport:
    schema_version: str
    status: Literal['EXPLORATORY_ONLY', 'INSUFFICIENT_EVIDENCE']
    locale: str
    context: Literal['professional', 'conversational']
    observation: FluencyObservation
    feedback: FluencyFeedback
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def validate_fluency_pipeline(
    audio: bytes, *, locale: str, context: Literal['professional', 'conversational'],
    consent: bool, minimum_pause_ms: int = 200,
    vad: Callable | None = None,
) -> FluencyValidationReport:
    """Validate VAD -> timing -> feedback end to end, locally.

    `vad` is an injectable test double; in normal execution the installed local
    Silero pipeline is used. No transcript and hence no word-rate inference.
    The caller must verify authenticated ownership and recording-bound consent.
    """
    if consent is not True:
        raise FluencyValidationError('Explicit recording-specific consent required')
    if context not in ('professional', 'conversational'):
        raise FluencyValidationError('Unsupported context')
    if type(minimum_pause_ms) is not int or not 0 <= minimum_pause_ms <= 60_000:
        raise FluencyValidationError('Invalid pause threshold')
    if type(audio) is not bytes or not audio:
        raise FluencyValidationError('Audio must be nonempty bytes')
    kwargs = dict(locale=locale, consent=True, minimum_pause_ms=minimum_pause_ms)
    if vad is not None:
        kwargs['vad'] = vad
    observation = observe_fluency_timing(audio, **kwargs)
    feedback = build_fluency_feedback(observation, context=context, minimum_pause_ms=minimum_pause_ms)
    expected_status = ('INSUFFICIENT_EVIDENCE' if observation.timing.status == 'INSUFFICIENT_EVIDENCE'
                       else 'OBSERVATIONAL_ONLY')
    if feedback.status != expected_status:
        raise FluencyValidationError('Observation and feedback disagree')
    if observation.locale != feedback.locale:
        raise FluencyValidationError('Feedback locale mismatch')
    if observation.timing.speaking_rate_wpm is not None or observation.timing.articulation_rate_wpm is not None:
        raise FluencyValidationError('Unverified word rates must not be produced')
    return FluencyValidationReport(
        'fluency-validation-v1',
        'INSUFFICIENT_EVIDENCE' if observation.timing.status == 'INSUFFICIENT_EVIDENCE' else 'EXPLORATORY_ONLY',
        locale, context, observation, feedback,
        ('Model execution is not independently calibrated accuracy.',
         'Likely speech, timing, and optional practice are not fluency or CEFR scores.',
         'No verified transcript or word count was supplied.',
         'No raw audio is stored by this service; FFmpeg decoder may use temporary files.',
         'Record ownership and consent binding must be enforced by the application.'),
    )
