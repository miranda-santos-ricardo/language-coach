"""Step 5.4a: fail-closed, authorized SQLAlchemy resolver for committed turns.

Read-only; caller supplies a request-scoped SQLAlchemy Session and authenticated UUID.
Never accepts learner text or user identity from an untrusted request body.
Voice provenance is NOT persisted in current ConversationTurn. When unknown,
allow only text-only review of persisted learner_text with explicit UNKNOWN origin.
"""
from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.conversation_turn_assessment import CommittedTurnSnapshot, TurnAssessmentError


def make_sqlalchemy_turn_resolver(
    db: Session,
    *,
    context_from_session: Callable[[object], str],
    voice_origin_from_turn: Callable[[object, object], tuple[str, bool] | None] | None = None,
    models: tuple[type, type, type, type] | None = None,
) -> Callable[[UUID, UUID, UUID], CommittedTurnSnapshot]:
    """Build a resolver bound to the authenticated request's DB session.

    `context_from_session` must map your trusted session/register metadata to
    'professional' or 'conversational'; no guess based on free-form scenario names.
    `voice_origin_from_turn` must read *trusted persisted* provenance, not request input.
    This is a boundary; caller must also enforce app authentication.
    `models` enables isolated SQLAlchemy integration tests without app settings imports.
    """
    if models is None:
        from app.models import ConversationTurn, PracticeSession, LanguageProfile, LanguageVariant
    else:
        ConversationTurn, PracticeSession, LanguageProfile, LanguageVariant = models
    if not callable(context_from_session) or not isinstance(db, Session):
        raise TurnAssessmentError('Trusted session and context resolver required')

    def resolve(user_id: UUID, session_id: UUID, turn_id: UUID) -> CommittedTurnSnapshot:
        if any(type(v) is not UUID for v in (user_id, session_id, turn_id)):
            raise TurnAssessmentError('Invalid identity reference')
        try:
            # Owner predicate is part of the SQL query, not a post-fetch Python check.
            result = db.execute(
                select(ConversationTurn, PracticeSession, LanguageProfile, LanguageVariant)
                .join(PracticeSession, ConversationTurn.practice_session_id == PracticeSession.id)
                .join(LanguageProfile, PracticeSession.language_profile_id == LanguageProfile.id)
                .join(LanguageVariant, LanguageProfile.language_variant_id == LanguageVariant.id)
                .where(
                    ConversationTurn.id == turn_id,
                    ConversationTurn.practice_session_id == session_id,
                    LanguageProfile.user_id == user_id,
                    PracticeSession.id == session_id,
                )
            ).one_or_none()
            if result is None:
                raise TurnAssessmentError('Turn unavailable')
            turn, practice, profile, variant = result
            if not isinstance(turn.learner_text, str) or not turn.learner_text.strip():
                raise TurnAssessmentError('Committed text unavailable')
            if turn.input_modality == 'text':
                origin, original = 'TYPED', False
            elif turn.input_modality == 'voice':
                # Never infer STT state from input_modality alone.
                evidence = (voice_origin_from_turn(turn, practice)
                            if voice_origin_from_turn is not None else None)
                if evidence is None:
                    origin, original = 'VOICE_TEXT_UNKNOWN', False
                elif (not isinstance(evidence, tuple) or len(evidence) != 2
                        or evidence[0] not in ('STT_UNEDITED', 'USER_EDITED', 'VOICE_TEXT_UNKNOWN')
                        or type(evidence[1]) is not bool
                        or (evidence[0] == 'STT_UNEDITED' and not evidence[1])
                        or (evidence[0] == 'VOICE_TEXT_UNKNOWN' and evidence[1])):
                    raise TurnAssessmentError('Invalid voice text provenance')
                else:
                    origin, original = evidence
            else:
                raise TurnAssessmentError('Unsupported modality')
            context = context_from_session(practice)
            if context not in ('professional', 'conversational'):
                raise TurnAssessmentError('Unmapped communication context')
            locale = variant.code
            if locale not in ('fr-CA', 'en-CA', 'en-US', 'en-GB'):
                raise TurnAssessmentError('Unsupported locale')
            scenario = practice.scenario_key or 'General conversation'
            if not isinstance(scenario, str) or not scenario.strip() or len(scenario) > 200:
                raise TurnAssessmentError('Invalid scenario')
            return CommittedTurnSnapshot(
                user_id=user_id, practice_session_id=session_id,
                conversation_turn_id=turn.id, client_request_id=turn.client_request_id,
                locale=locale, context=context, scenario=scenario,
                text=turn.learner_text, origin=origin,
                stt_original_available=original, committed=True, learner_turn=True,
            )
        except TurnAssessmentError:
            raise
        except Exception as exc:
            raise TurnAssessmentError('Authorized SQLAlchemy lookup failed') from exc
    return resolve
