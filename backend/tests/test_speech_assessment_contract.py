"""Phase 7 contract tests: zero provider calls or database access."""
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.schemas.speech_assessment import (
    AudioEvidence, AssessmentDimension, AssessmentEvidence, SpeechAssessment,
    AssessmentStatus, DimensionStatus, EvidenceKind, RetentionMode,
)


def test_audio_is_ephemeral_by_default():
    audio = AudioEvidence(recording_attempt_id=uuid4(), mime_type="audio/webm", size_bytes=10)
    assert audio.retention_mode == RetentionMode.EPHEMERAL
    assert audio.storage_reference is None


def test_retention_requires_explicit_consent():
    with pytest.raises(ValidationError):
        AudioEvidence(recording_attempt_id=uuid4(), mime_type="audio/webm", size_bytes=10,
                      retention_mode=RetentionMode.EXPLICIT_RETENTION)


def test_numeric_measurement_requires_method_and_unit():
    with pytest.raises(ValidationError):
        AssessmentEvidence(evidence_id=uuid4(), kind=EvidenceKind.MEASURED,
                           source="AUDIO", description="pause", numeric_value=1.3)


def test_unassessed_dimension_cannot_have_score():
    with pytest.raises(ValidationError):
        AssessmentDimension(name="pronunciation_accuracy", status=DimensionStatus.NOT_ASSESSED,
                            score=90, explanation="not analyzed")


def test_audio_dimension_requires_original_audio():
    evidence_id = uuid4()
    base = dict(assessment_id=uuid4(), user_id=uuid4(), language_profile_id=uuid4(),
                practice_session_id=uuid4(), conversation_turn_id=uuid4(),
                client_request_id=uuid4(), locale="fr-CA", cefr_level="B2",
                scenario="Banking meeting", stt_transcript="bonjour", submitted_text="Bonjour.",
                status=AssessmentStatus.COMPLETED, rubric_version="speech-v1",
                evidence=[AssessmentEvidence(evidence_id=evidence_id, kind=EvidenceKind.MEASURED,
                    source="AUDIO", description="Duration", numeric_value=2, unit="s", method="decoder")],
                dimensions=[AssessmentDimension(name="pausing", status=DimensionStatus.ASSESSED,
                    evidence_ids=[evidence_id], explanation="Audio-derived metric")])
    with pytest.raises(ValidationError):
        SpeechAssessment(**base)
    base["audio"] = AudioEvidence(recording_attempt_id=uuid4(), mime_type="audio/webm", size_bytes=100)
    assert SpeechAssessment(**base).status == AssessmentStatus.COMPLETED


def test_unknown_evidence_reference_rejected():
    with pytest.raises(ValidationError):
        SpeechAssessment(assessment_id=uuid4(),user_id=uuid4(),language_profile_id=uuid4(),
            practice_session_id=uuid4(),conversation_turn_id=uuid4(),client_request_id=uuid4(),
            locale="en-CA",cefr_level="C1",scenario="Interview",stt_transcript="hello",
            submitted_text="hello",status=AssessmentStatus.PARTIAL,rubric_version="speech-v1",
            dimensions=[AssessmentDimension(name="clarity",status=DimensionStatus.ASSESSED,
                evidence_ids=[uuid4()],explanation="Well-structured")])
