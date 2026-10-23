"""Phase 7 Step 4.4 — evidence-bound, non-diagnostic timing feedback.

Text generation is deterministic and offline. No CEFR, fluency scoring, accent
judgement, audio, transcript, persistence, API, or personalization inference.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal

from app.services.fluency_runtime_integration import FluencyObservation


class FluencyFeedbackError(ValueError):
    pass


@dataclass(frozen=True)
class FeedbackItem:
    code: str
    kind: Literal['observation', 'practice', 'limitation']
    message: str


@dataclass(frozen=True)
class FluencyFeedback:
    schema_version: str
    locale: str
    context: Literal['professional', 'conversational']
    status: Literal['OBSERVATIONAL_ONLY', 'INSUFFICIENT_EVIDENCE']
    items: tuple[FeedbackItem, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


_FR = {
    'insufficient': "Il n'y a pas assez de données vocales pour décrire le rythme de cet enregistrement.",
    'speech': "Le détecteur a repéré environ {seconds} secondes de parole probable dans cet enregistrement.",
    'pauses_none': "Aucune pause interne d'au moins {threshold} ms n'a été détectée entre les segments de parole probable.",
    'pauses': "{count} pause(s) interne(s) d'au moins {threshold} ms ont été repérées entre les segments de parole probable.",
    'practice_professional': "Pour vous exercer, enregistrez à nouveau une courte présentation professionnelle en marquant volontairement les transitions entre les idées, puis écoutez le rythme.",
    'practice_conversational': "Pour vous exercer, reformulez une courte idée à voix haute, puis réécoutez les pauses et le rythme sans chercher à parler plus vite.",
    'limitation': "Ces observations proviennent d'un détecteur non calibré sur des annotations humaines; elles ne mesurent ni la fluidité globale ni la prononciation.",
}
_EN = {
    'insufficient': "There is not enough speech evidence to describe the timing of this recording.",
    'speech': "The detector identified approximately {seconds} seconds of likely speech in this recording.",
    'pauses_none': "No internal pauses of at least {threshold} ms were detected between likely-speech segments.",
    'pauses': "{count} internal pause(s) of at least {threshold} ms were detected between likely-speech segments.",
    'practice_professional': "For practice, record a short professional update, deliberately marking transitions between ideas, then listen to its pacing.",
    'practice_conversational': "For practice, rephrase a short idea aloud and listen to the pauses and pacing without trying to speak faster.",
    'limitation': "These observations use a detector not calibrated against independent human annotations; they do not assess overall fluency or pronunciation.",
}


def build_fluency_feedback(
    observation: FluencyObservation, *, context: Literal['professional', 'conversational'],
    minimum_pause_ms: int = 200,
) -> FluencyFeedback:
    """Produce cautious feedback from Step 4.3 observation, not proficiency advice.

    Requires upstream consent and recording ownership validation. This function
    neither accepts raw audio nor verifies that VAD segments correspond to speech.
    """
    if type(observation) is not FluencyObservation:
        raise FluencyFeedbackError('Expected a FluencyObservation')
    if context not in ('professional', 'conversational'):
        raise FluencyFeedbackError('Unsupported communication context')
    if type(minimum_pause_ms) is not int or not 0 <= minimum_pause_ms <= 60_000:
        raise FluencyFeedbackError('Invalid pause threshold')
    if observation.locale not in ('fr-CA', 'en-CA', 'en-US', 'en-GB'):
        raise FluencyFeedbackError('Unsupported locale')
    if observation.status != 'EXPLORATORY_ONLY' or observation.detector != 'silero-vad-local' or observation.schema_version != 'fluency-observation-v1':
        raise FluencyFeedbackError('Unsupported observation provenance')
    metrics = observation.timing
    if metrics.locale != observation.locale or metrics.method != 'speech-temporal-v0.1':
        raise FluencyFeedbackError('Inconsistent temporal evidence')
    messages = _FR if observation.locale == 'fr-CA' else _EN
    limitations = (messages['limitation'], 'No CEFR, fluency grade, pronunciation grade, or accent judgment is inferred.')
    if metrics.status == 'INSUFFICIENT_EVIDENCE':
        if metrics.speech_duration_ms is not None or metrics.speech_intervals:
            raise FluencyFeedbackError('Inconsistent insufficient evidence')
        return FluencyFeedback('fluency-feedback-v1', observation.locale, context,
            'INSUFFICIENT_EVIDENCE',
            (FeedbackItem('insufficient_evidence','limitation',messages['insufficient']),),limitations)
    if metrics.status != 'MEASURED' or type(metrics.speech_duration_ms) is not int or metrics.speech_duration_ms <= 0:
        raise FluencyFeedbackError('Invalid measured timing')
    if not metrics.speech_intervals or metrics.internal_pause_duration_ms is None:
        raise FluencyFeedbackError('Incomplete measured timing')
    # Do not assume that user supplied the same pause threshold at measure time.
    # Calculate threshold-dependent intervals afresh from adjacent raw segments.
    durations = [b.start_ms - a.end_ms for a, b in zip(metrics.speech_intervals, metrics.speech_intervals[1:])]
    if any(type(x) is not int or x < 0 for x in durations):
        raise FluencyFeedbackError('Invalid temporal intervals')
    count = sum(d >= minimum_pause_ms for d in durations)
    seconds = f'{metrics.speech_duration_ms / 1000:.1f}'
    items = (
        FeedbackItem('likely_speech_duration','observation', messages['speech'].format(seconds=seconds)),
        FeedbackItem('internal_pauses','observation',
                     (messages['pauses'] if count else messages['pauses_none']).format(count=count,threshold=minimum_pause_ms)),
        FeedbackItem('optional_practice','practice', messages['practice_'+context]),
        FeedbackItem('uncalibrated_vad','limitation',messages['limitation']),
    )
    return FluencyFeedback('fluency-feedback-v1',observation.locale,context,'OBSERVATIONAL_ONLY',items,limitations)
