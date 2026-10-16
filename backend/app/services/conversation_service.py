"""Phase 5 Step 6.2: serialized per-session conversation orchestration."""
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ConversationTurn, LanguageFeedback
from app.repositories.conversation_turn import ConversationTurnRepository
from app.services.conversation_lock import conversation_execution_gate, ConversationBusyError
from app.services.conversation_context import ConversationContextResolver
from app.services.conversation_prompt import ConversationPromptBuilder
from app.services.llm import ConversationLLM, LLMMessage
from app.services.structured_feedback import CoachTurnOutput, StructuredFeedbackValidator


class InvalidLearnerUtteranceError(ValueError):
    """Text/modality does not satisfy basic input requirements."""


class ConversationRequestConflictError(ValueError):
    """The same request ID was previously used with different input."""


@dataclass(frozen=True)
class ConversationOutcome:
    turn_id: uuid.UUID
    turn_index: int
    coach_response: str
    feedback: CoachTurnOutput
    replayed: bool
    prompt_version: str | None
    model: str | None


class ConversationService:
    def __init__(self, *, llm: ConversationLLM,
                 context_resolver: ConversationContextResolver | None = None,
                 prompt_builder: ConversationPromptBuilder | None = None,
                 feedback_validator: StructuredFeedbackValidator | None = None,
                 max_input_chars: int = 4000) -> None:
        if max_input_chars < 1:
            raise ValueError("max_input_chars must be positive")
        self.llm = llm
        self.context_resolver = context_resolver or ConversationContextResolver()
        self.prompt_builder = prompt_builder or ConversationPromptBuilder()
        self.feedback_validator = feedback_validator or StructuredFeedbackValidator()
        self.max_input_chars = max_input_chars

    def submit(self, *, session: Session, user_id: uuid.UUID, profile_id: uuid.UUID,
               practice_session_id: uuid.UUID, text: str, input_modality: str,
               client_request_id: uuid.UUID) -> ConversationOutcome:
        if not isinstance(text, str) or not text.strip() or len(text) > self.max_input_chars:
            raise InvalidLearnerUtteranceError("Learner text is invalid")
        if input_modality not in ("text", "voice"):
            raise InvalidLearnerUtteranceError("Input modality is invalid")
        if not isinstance(client_request_id, uuid.UUID):
            raise InvalidLearnerUtteranceError("Request ID must be a UUID")
        learner_text = text.strip()

        with conversation_execution_gate(session, practice_session_id):
            try:
                # Check authorization and ACTIVE status before any provider request.
                context = self.context_resolver.resolve(
                    session=session, user_id=user_id, profile_id=profile_id,
                    practice_session_id=practice_session_id)
    
                # Recheck the committed request after acquiring the gate.
                existing = ConversationTurnRepository.get_by_request_id(
                    session, user_id, profile_id, practice_session_id, client_request_id)
                if existing is not None:
                    if existing.learner_text != learner_text or existing.input_modality != input_modality:
                        raise ConversationRequestConflictError("Request ID already used with different input")
                    return ConversationOutcome(
                        turn_id=existing.id, turn_index=existing.turn_index,
                        coach_response=existing.coach_response,
                        feedback=self._restore_output(existing), replayed=True,
                        prompt_version=None, model=None)
    
                prompt = self.prompt_builder.build(context)
                result = self.llm.generate(
                    instructions=prompt.instructions,
                    messages=[*context.recent_messages, LLMMessage(role="user", content=learner_text)],
                )
                parsed = self.feedback_validator.validate(result)
                feedback = parsed.feedback
                # Commit both records atomically; PostgreSQL gate uses the transaction.
                try:
                    next_index = (session.scalar(select(func.max(ConversationTurn.turn_index)).where(
                        ConversationTurn.practice_session_id == practice_session_id)) or 0) + 1
                    turn = ConversationTurn(
                        practice_session_id=practice_session_id,
                        turn_index=next_index, client_request_id=client_request_id,
                        input_modality=input_modality, learner_text=learner_text,
                        coach_response=parsed.coach_response,
                    )
                    stored_feedback = LanguageFeedback(
                        overall_assessment=feedback.overall_assessment,
                        grammar_feedback=feedback.grammar.model_dump(),
                        vocabulary_feedback=feedback.vocabulary.model_dump(),
                        clarity_feedback=feedback.clarity.model_dump(),
                        naturalness_feedback=feedback.naturalness.model_dump(),
                        register_feedback=feedback.register_feedback.model_dump(),
                        improved_version=feedback.improved_version,
                        explanations=feedback.explanations,
                        strengths=feedback.strengths,
                        next_recommendation=feedback.next_recommendation,
                    )
                    ConversationTurnRepository.add_with_feedback(session, turn, stored_feedback)
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                return ConversationOutcome(
                    turn_id=turn.id, turn_index=turn.turn_index,
                    coach_response=parsed.coach_response,
                    feedback=parsed, replayed=False, prompt_version=prompt.version,
                    model=result.model)
            finally:
                # Replay, validation failures, and provider failures must release
                # transaction-scoped PostgreSQL locks as well as DB resources.
                if session.in_transaction():
                    session.rollback()
    @staticmethod
    def _restore_output(turn: ConversationTurn) -> CoachTurnOutput:
        fb = turn.feedback
        if fb is None:
            raise ValueError("Stored conversation feedback is missing")
        return CoachTurnOutput.model_validate({
            "coach_response": turn.coach_response,
            "feedback": {
                "overall_assessment": fb.overall_assessment,
                "grammar": fb.grammar_feedback,
                "vocabulary": fb.vocabulary_feedback,
                "clarity": fb.clarity_feedback,
                "naturalness": fb.naturalness_feedback,
                "register": fb.register_feedback,
                "improved_version": fb.improved_version,
                "explanations": fb.explanations,
                "strengths": fb.strengths,
                "next_recommendation": fb.next_recommendation,
            },
        })
