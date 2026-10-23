from dataclasses import replace
from uuid import uuid4
import pytest
from app.services.conversational_evidence import (
    ConversationalEvidence, ConversationalEvidenceError, DimensionObservation, DIMENSIONS,
    build_evidence_gate, accept_reviewed_observations,
)


def sample(**changes):
    values = dict(user_id=uuid4(), practice_session_id=uuid4(), conversation_turn_id=uuid4(),
                  client_request_id=uuid4(), locale='fr-CA', context='professional',
                  scenario='Project status update', text='Nous présentons les risques et les mesures.',
                  origin='USER_EDITED', authorized_turn=True, stt_original_available=True)
    values.update(changes)
    return ConversationalEvidence(**values)


@pytest.mark.parametrize('locale', ['fr-CA','en-CA','en-US','en-GB'])
def test_supported_locale(locale):
    draft = build_evidence_gate(sample(locale=locale))
    assert draft.locale == locale and draft.status == 'AWAITING_EVALUATOR'
    assert all(d.status == 'NOT_ASSESSED' for d in draft.dimensions)


def test_no_scoring():
    assert all('score' not in vars(d) for d in build_evidence_gate(sample()).dimensions)


def test_short_text_abstains():
    d = build_evidence_gate(sample(text='Bonjour.'))
    assert d.status == 'INSUFFICIENT_EVIDENCE'
    assert all(x.status == 'INSUFFICIENT_EVIDENCE' for x in d.dimensions)


@pytest.mark.parametrize('changes', [
    {'authorized_turn':False}, {'authorized_turn':1}, {'locale':'fr-FR'},
    {'context':'executive'}, {'origin':'UNKNOWN'}, {'text':''}, {'text':'x'*10001},
    {'scenario':' '}, {'stt_original_available':'yes'},
    {'origin':'STT_UNEDITED','stt_original_available':False}, {'user_id':'not-uuid'},
])
def test_rejects_bad_evidence(changes):
    with pytest.raises(ConversationalEvidenceError): sample(**changes)


def reviewed(kind='HUMAN_REVIEWED'):
    return tuple(DimensionObservation(d, kind if i == 0 else 'NOT_ASSESSED',
        'Reviewer finding' if i == 0 else 'No review', 'risques' if i == 0 else None)
        for i,d in enumerate(DIMENSIONS))


@pytest.mark.parametrize('kind', ['HUMAN_REVIEWED', 'MODEL_JUDGMENT'])
def test_review_with_quote(kind):
    result = accept_reviewed_observations(sample(), reviewed(kind), reviewer_kind=kind, evaluator_version='reviewer-v1')
    assert result.status == 'REVIEWED' and result.dimensions[0].supporting_quote == 'risques'


def test_quote_not_in_transcript_rejected():
    obs = list(reviewed())
    obs[0] = replace(obs[0], supporting_quote='unquoted assertion')
    with pytest.raises(ConversationalEvidenceError):
        accept_reviewed_observations(sample(), tuple(obs), reviewer_kind='HUMAN_REVIEWED', evaluator_version='v1')


def test_kind_mismatch_rejected():
    with pytest.raises(ConversationalEvidenceError):
        accept_reviewed_observations(sample(), reviewed(), reviewer_kind='MODEL_JUDGMENT', evaluator_version='v1')


def test_duplicates_and_order_rejected():
    with pytest.raises(ConversationalEvidenceError):
        accept_reviewed_observations(sample(), tuple(reversed(reviewed())), reviewer_kind='HUMAN_REVIEWED', evaluator_version='v1')


def test_unversioned_rejected():
    with pytest.raises(ConversationalEvidenceError):
        accept_reviewed_observations(sample(), reviewed(), reviewer_kind='HUMAN_REVIEWED', evaluator_version='')


def test_insufficient_text_reviewer_cannot_override():
    with pytest.raises(ConversationalEvidenceError):
        accept_reviewed_observations(sample(text='risques'), reviewed(), reviewer_kind='HUMAN_REVIEWED', evaluator_version='v1')


def test_no_audio_or_api_required():
    value = build_evidence_gate(sample())
    assert value.text_origin == 'USER_EDITED'
    assert len(value.dimensions) == 5


def test_unassessed_cannot_cite_quote():
    with pytest.raises(ConversationalEvidenceError):
        DimensionObservation('clarity', 'NOT_ASSESSED', 'Not assessed', 'texte')


def test_review_requires_quote():
    with pytest.raises(ConversationalEvidenceError):
        DimensionObservation('clarity', 'MODEL_JUDGMENT', 'Good')
