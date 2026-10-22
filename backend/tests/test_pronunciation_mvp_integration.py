from dataclasses import replace
from uuid import uuid4

import pytest

from app.schemas.speech_assessment import AssessmentStatus, DimensionStatus, RetentionMode
from app.services.pronunciation_assessment import (
    PronunciationOutcome, PronunciationResult,
)
from app.services.pronunciation_mvp_integration import (
    AuthorizedTurnContext, IntegratePronunciationCommand, IntegrationRejected,
    PronunciationMvpIntegrator,
)


def make_case():
    user, turn, session, profile = (uuid4() for _ in range(4))
    ctx = AuthorizedTurnContext(
        user_id=user, language_profile_id=profile, practice_session_id=session,
        conversation_turn_id=turn, locale='fr-CA', cefr_level='B2', scenario='Meeting',
        stt_transcript='Bonjour', submitted_text='Bonjour.',
        is_voice_turn=True, is_session_active=True,
    )
    command = IntegratePronunciationCommand(user, turn, uuid4(), uuid4(), b'not-a-real-wave', 'audio/webm', True)
    calls = []
    def resolver(requester, turn_id):
        calls.append((requester, turn_id))
        return ctx
    return ctx, command, calls, resolver


def test_successful_abstention_and_audio_provenance():
    ctx, cmd, calls, resolver = make_case()
    result = PronunciationMvpIntegrator(resolve_authorized_turn=resolver).run(cmd)
    assert result.status == AssessmentStatus.INSUFFICIENT_EVIDENCE
    assert result.dimensions[0].status == DimensionStatus.NOT_ASSESSED
    assert result.dimensions[0].score is None
    assert result.audio.recording_attempt_id == cmd.recording_attempt_id
    assert result.audio.retention_mode == RetentionMode.EPHEMERAL
    assert result.audio.storage_reference is None
    assert result.audio.sha256_hex and len(result.audio.sha256_hex) == 64
    assert result.stt_transcript != result.submitted_text
    assert result.evidence == []
    assert calls == [(cmd.requester_user_id, cmd.conversation_turn_id)]


def test_idempotent_and_reauthorizes():
    _, cmd, calls, resolver = make_case()
    runner = PronunciationMvpIntegrator(resolve_authorized_turn=resolver)
    one, two = runner.run(cmd), runner.run(cmd)
    assert one.assessment_id == two.assessment_id and len(calls) == 2
    one.dimensions.clear()
    assert len(runner.run(cmd).dimensions) == 1

@pytest.mark.parametrize('field, value', [
    ('recording_attempt_id', uuid4()), ('mime_type', 'audio/wav'), ('audio', b'other'),
])
def test_idempotency_conflict(field, value):
    _, cmd, _, resolver = make_case()
    runner = PronunciationMvpIntegrator(resolve_authorized_turn=resolver)
    runner.run(cmd)
    with pytest.raises(IntegrationRejected, match='Idempotency conflict'):
        runner.run(replace(cmd, **{field: value}))


def test_denied_user():
    ctx, cmd, _, _ = make_case()
    bad = replace(ctx, user_id=uuid4())
    runner = PronunciationMvpIntegrator(resolve_authorized_turn=lambda *_: bad)
    with pytest.raises(IntegrationRejected, match='not eligible'):
        runner.run(cmd)

@pytest.mark.parametrize('change', [
    {'is_voice_turn': False}, {'is_session_active': False},
    {'conversation_turn_id': uuid4()},
])
def test_ineligible_turn(change):
    ctx, cmd, _, _ = make_case()
    runner = PronunciationMvpIntegrator(resolve_authorized_turn=lambda *_: replace(ctx, **change))
    with pytest.raises(IntegrationRejected):
        runner.run(cmd)

@pytest.mark.parametrize('change', [
    {'processing_consent': False}, {'audio': b''},
    {'audio': 'bad'}, {'mime_type': 'text/plain'},
    {'audio': b'x' * (10*1024*1024+1)},
], ids=['no-consent','empty','not-bytes','mime','oversized'])
def test_reject_invalid_input(change):
    _, cmd, _, resolver = make_case()
    with pytest.raises(IntegrationRejected):
        PronunciationMvpIntegrator(resolve_authorized_turn=resolver).run(replace(cmd, **change))

@pytest.mark.parametrize('locale', ['fr-CA', 'en-CA', 'en-US', 'en-GB'])
def test_supported_locales(locale):
    ctx, cmd, _, _ = make_case()
    runner = PronunciationMvpIntegrator(resolve_authorized_turn=lambda *_: replace(ctx, locale=locale))
    assert runner.run(cmd).locale == locale


def test_unsupported_locale_rejected():
    ctx, cmd, _, _ = make_case()
    runner = PronunciationMvpIntegrator(resolve_authorized_turn=lambda *_: replace(ctx, locale='de-DE'))
    with pytest.raises(ValueError, match='Unsupported locale'):
        runner.run(cmd)


def test_provider_error_not_cached():
    _, cmd, _, resolver = make_case()
    class Flaky:
        n = 0
        def assess(self, request):
            self.n += 1
            if self.n == 1:
                raise RuntimeError('provider unavailable')
            from app.services.pronunciation_assessment import LocalEvidenceGateProvider
            return LocalEvidenceGateProvider().assess(request)
    provider = Flaky()
    runner = PronunciationMvpIntegrator(resolve_authorized_turn=resolver, provider=provider)
    with pytest.raises(RuntimeError):
        runner.run(cmd)
    assert runner.run(cmd).status == AssessmentStatus.INSUFFICIENT_EVIDENCE
    assert provider.n == 2


def test_provider_cannot_inject_score():
    _, cmd, _, resolver = make_case()
    class Invalid:
        def assess(self, request):
            return PronunciationResult(PronunciationOutcome.ASSESSED, 'invalid', '0', request.locale, 'x', ())
    with pytest.raises(IntegrationRejected, match='Uncalibrated'):
        PronunciationMvpIntegrator(resolve_authorized_turn=resolver, provider=Invalid()).run(cmd)


def test_reauthorization_on_replay_after_session_completed():
    ctx, cmd, _, _ = make_case()
    state = {'active': True}
    runner = PronunciationMvpIntegrator(resolve_authorized_turn=lambda *_: replace(ctx, is_session_active=state['active']))
    runner.run(cmd)
    state['active'] = False
    with pytest.raises(IntegrationRejected):
        runner.run(cmd)
