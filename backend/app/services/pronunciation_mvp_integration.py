"""Phase 7 Step 3.4: offline, evidence-gated integration seam (NOT a production API).

Caller injects a trusted authorization callback that verifies ownership, lifecycle,
and the recording-to-turn association. No database or network access is performed.
No raw audio is persisted; idempotency is process-local and not durable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from threading import RLock
from typing import Callable
from uuid import UUID, uuid4

from app.schemas.speech_assessment import (
    AssessmentStatus, AudioEvidence, DimensionStatus, RetentionMode, SpeechAssessment,
)
from app.services.pronunciation_assessment import (
    LocalEvidenceGateProvider, PronunciationAssessmentProvider, PronunciationRequest,
    PronunciationOutcome,
)


class IntegrationRejected(ValueError):
    """Do not leak raw audio or learner transcript in errors."""


@dataclass(frozen=True)
class AuthorizedTurnContext:
    """Must be produced by a trusted owner/session/turn resolver, never user input."""
    user_id: UUID
    language_profile_id: UUID
    practice_session_id: UUID
    conversation_turn_id: UUID
    locale: str
    cefr_level: str
    scenario: str
    stt_transcript: str
    submitted_text: str
    is_voice_turn: bool
    is_session_active: bool


@dataclass(frozen=True)
class IntegratePronunciationCommand:
    requester_user_id: UUID
    conversation_turn_id: UUID
    recording_attempt_id: UUID
    client_request_id: UUID
    audio: bytes
    mime_type: str
    processing_consent: bool


class PronunciationMvpIntegrator:
    """Minimal in-process seam. Not a replacement for transactional DB idempotency."""

    def __init__(
        self,
        *,
        resolve_authorized_turn: Callable[[UUID, UUID], AuthorizedTurnContext],
        provider: PronunciationAssessmentProvider | None = None,
    ) -> None:
        self._resolve = resolve_authorized_turn
        self._provider = provider if provider is not None else LocalEvidenceGateProvider()
        self._lock = RLock()
        # Cache only assessments and hashes; NEVER raw audio.
        self._completed: dict[tuple[UUID, UUID, UUID], tuple[str, SpeechAssessment]] = {}

    def run(self, command: IntegratePronunciationCommand) -> SpeechAssessment:
        if not command.processing_consent:
            raise IntegrationRejected('Explicit audio processing consent is required')
        if not isinstance(command.audio, bytes) or not 0 < len(command.audio) <= 10 * 1024 * 1024:
            raise IntegrationRejected('Invalid audio')
        if command.mime_type not in {'audio/wav', 'audio/wave', 'audio/webm', 'audio/mp4'}:
            raise IntegrationRejected('Unsupported audio MIME type')
        key = (command.requester_user_id, command.conversation_turn_id, command.client_request_id)
        digest = sha256(command.audio).hexdigest()
        # Serialize inside this one process; deployments must use DB-level coordination.
        with self._lock:
            # Always re-authorize, including repeated submissions.
            ctx = self._resolve(command.requester_user_id, command.conversation_turn_id)
            if (ctx.user_id != command.requester_user_id or ctx.conversation_turn_id != command.conversation_turn_id
                    or not ctx.is_voice_turn or not ctx.is_session_active):
                raise IntegrationRejected('Turn is not eligible for assessment')
            existing = self._completed.get(key)
            if existing is not None:
                fingerprint, assessment = existing
                if fingerprint != self._fingerprint(command, digest):
                    raise IntegrationRejected('Idempotency conflict')
                return assessment.model_copy(deep=True)
            # Locale, consent, size and reference validated by provider request.
            request = PronunciationRequest(
                audio=command.audio, locale=ctx.locale,
                reference_text=None, processing_consent=command.processing_consent,
            )
            result = self._provider.assess(request)
            if result.outcome == PronunciationOutcome.ASSESSED:
                raise IntegrationRejected('Uncalibrated assessment cannot be recorded as assessed')
            dimension = result.as_dimension()
            if dimension.status == DimensionStatus.ASSESSED or dimension.score is not None:
                raise IntegrationRejected('Score not supported by current integration')
            audio_meta = AudioEvidence(
                recording_attempt_id=command.recording_attempt_id,
                mime_type=command.mime_type,
                size_bytes=len(command.audio),
                sha256_hex=digest,
                retention_mode=RetentionMode.EPHEMERAL,
                retention_consent=False,
            )
            assessment = SpeechAssessment(
                assessment_id=uuid4(), user_id=ctx.user_id,
                language_profile_id=ctx.language_profile_id,
                practice_session_id=ctx.practice_session_id,
                conversation_turn_id=ctx.conversation_turn_id,
                client_request_id=command.client_request_id,
                locale=ctx.locale, cefr_level=ctx.cefr_level, scenario=ctx.scenario,
                stt_transcript=ctx.stt_transcript, submitted_text=ctx.submitted_text,
                audio=audio_meta, status=AssessmentStatus.INSUFFICIENT_EVIDENCE,
                dimensions=[dimension], evidence=[], rubric_version='pronunciation-gate-v1',
                provider_version=f'{result.provider}:{result.provider_version}',
                assessed_at=datetime.now(timezone.utc),
            )
            self._completed[key] = (self._fingerprint(command, digest), assessment)
            return assessment.model_copy(deep=True)

    @staticmethod
    def _fingerprint(command: IntegratePronunciationCommand, digest: str) -> str:
        # Binding includes recording identity and MIME; no plaintext audio in cache.
        content = '|'.join((str(command.recording_attempt_id), command.mime_type, digest))
        return sha256(content.encode()).hexdigest()
