from dataclasses import replace
from uuid import uuid4
import pytest
from app.services.conversational_evidence import ConversationalEvidence, ConversationalEvidenceError, build_evidence_gate
from app.services.controlled_conversational_evaluator import prepare_evaluation_request
from app.services.sqlalchemy_turn_resolver import make_sqlalchemy_turn_resolver
from app.services.conversation_turn_assessment import TurnAssessmentError
from tests.test_sqlalchemy_turn_resolver import store, resolver, Turn


def evidence(origin='VOICE_TEXT_UNKNOWN', original=False, text='Je recommande une approche progressive et mesurée.'):
    return ConversationalEvidence(user_id=uuid4(), practice_session_id=uuid4(), conversation_turn_id=uuid4(),
        client_request_id=uuid4(), locale='fr-CA', context='professional', scenario='Executive update',
        text=text, origin=origin, authorized_turn=True, stt_original_available=original)


def test_unknown_voice_evidence_accepted():
    e=evidence(); assert build_evidence_gate(e).status == 'AWAITING_EVALUATOR'


def test_unknown_voice_short_text_abstains():
    assert build_evidence_gate(evidence(text='Bonjour')).status == 'INSUFFICIENT_EVIDENCE'


def test_unknown_voice_cannot_claim_original():
    with pytest.raises(ConversationalEvidenceError): evidence(original=True)


def test_stt_unedited_still_needs_original_proof():
    with pytest.raises(ConversationalEvidenceError): evidence(origin='STT_UNEDITED')


def test_verified_stt_allowed():
    assert evidence(origin='STT_UNEDITED', original=True).origin == 'STT_UNEDITED'


def test_user_edited_still_allowed():
    assert evidence(origin='USER_EDITED').origin == 'USER_EDITED'


def test_typed_still_allowed():
    assert evidence(origin='TYPED').origin == 'TYPED'


def test_prompt_explicitly_constrains_unknown():
    req=prepare_evaluation_request(evidence(), scenario_type='executive_update')
    assert 'VOICE_TEXT_UNKNOWN' in req.system_instructions
    assert 'VOICE_TEXT_UNKNOWN' in req.user_payload
    assert 'never claim' in req.system_instructions


def test_sql_voice_without_provenance_returns_unknown(store):
    db,(owner,other,_,session,turn_id)=store
    db.get(Turn,turn_id).input_modality='voice'; db.flush()
    snap=resolver(db)(owner,session,turn_id)
    assert snap.origin=='VOICE_TEXT_UNKNOWN' and snap.stt_original_available is False


def test_sql_voice_unknown_explicit_from_authority(store):
    db,(owner,other,_,session,turn_id)=store
    db.get(Turn,turn_id).input_modality='voice'; db.flush()
    snap=resolver(db,voice_origin_from_turn=lambda t,s:('VOICE_TEXT_UNKNOWN',False))(owner,session,turn_id)
    assert snap.origin=='VOICE_TEXT_UNKNOWN'


def test_sql_voice_known_edited_unchanged(store):
    db,(owner,other,_,session,turn_id)=store
    db.get(Turn,turn_id).input_modality='voice'; db.flush()
    assert resolver(db,voice_origin_from_turn=lambda t,s:('USER_EDITED',False))(owner,session,turn_id).origin=='USER_EDITED'


def test_sql_voice_invalid_provenance_denied(store):
    db,(owner,other,_,session,turn_id)=store
    db.get(Turn,turn_id).input_modality='voice'; db.flush()
    with pytest.raises(TurnAssessmentError):
        resolver(db,voice_origin_from_turn=lambda t,s:('VOICE_TEXT_UNKNOWN',True))(owner,session,turn_id)


def test_sql_cross_user_denied_even_voice_unknown(store):
    db,(owner,other,_,session,turn_id)=store
    db.get(Turn,turn_id).input_modality='voice'; db.flush()
    with pytest.raises(TurnAssessmentError): resolver(db)(other,session,turn_id)
