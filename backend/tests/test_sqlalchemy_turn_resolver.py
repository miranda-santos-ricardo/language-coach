"""SQLite integration tests exercise the actual SQL joins and owner filters."""
from uuid import uuid4
import pytest
from sqlalchemy import ForeignKey, String, Uuid, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from app.services.sqlalchemy_turn_resolver import make_sqlalchemy_turn_resolver
from app.services.conversation_turn_assessment import TurnAssessmentError

from tests.support.sqlalchemy_resolver_fixtures import (
    Base, Profile, Variant, Practice, Turn, store, resolver,
)

def test_actual_authorized_sql_join(store):
    db,(owner,_,_,session,turn)=store
    snap=resolver(db)(owner,session,turn)
    assert snap.user_id==owner and snap.origin=='TYPED' and snap.locale=='fr-CA'
    assert snap.text=='Voici les prochaines étapes du projet.'

def test_cross_user_returns_same_safe_error(store):
    db,(owner,other,_,session,turn)=store
    with pytest.raises(TurnAssessmentError,match='Turn unavailable'):
        resolver(db)(other,session,turn)

def test_invalid_turn_id_denied(store):
    db,(owner,_,_,session,_)=store
    with pytest.raises(TurnAssessmentError,match='Turn unavailable'):
        resolver(db)(owner,session,uuid4())

def test_invalid_session_id_denied(store):
    db,(owner,_,_,_,turn)=store
    with pytest.raises(TurnAssessmentError,match='Turn unavailable'):
        resolver(db)(owner,uuid4(),turn)

def test_voice_without_persisted_provenance_allows_text_only(store):
    db,(owner,_,_,session,turn_id)=store
    db.get(Turn,turn_id).input_modality='voice';db.flush()
    snap=resolver(db)(owner,session,turn_id)
    assert snap.origin == 'VOICE_TEXT_UNKNOWN'
    assert snap.stt_original_available is False
    assert snap.text == 'Voici les prochaines étapes du projet.'

def test_voice_trusted_provenance(store):
    db,(owner,_,_,session,turn_id)=store
    db.get(Turn,turn_id).input_modality='voice';db.flush()
    snap=resolver(db,voice_origin_from_turn=lambda t,s:('USER_EDITED',False))(owner,session,turn_id)
    assert snap.origin=='USER_EDITED' and not snap.stt_original_available

def test_false_stt_provenance_denied(store):
    db,(owner,_,_,session,turn_id)=store
    db.get(Turn,turn_id).input_modality='voice';db.flush()
    with pytest.raises(TurnAssessmentError,match='Invalid voice text provenance'):
        resolver(db,voice_origin_from_turn=lambda t,s:('STT_UNEDITED',False))(owner,session,turn_id)

def test_missing_context_fails_closed(store):
    db,(owner,_,_,session,turn)=store
    fn=make_sqlalchemy_turn_resolver(db,context_from_session=lambda _: 'guess',
                                    models=(Turn,Practice,Profile,Variant))
    with pytest.raises(TurnAssessmentError,match='Unmapped communication context'):
        fn(owner,session,turn)

def test_unknown_locale_fails_closed(store):
    db,(owner,_,_,session,turn)=store
    db.get(Variant,1).code='xx-XX';db.flush()
    with pytest.raises(TurnAssessmentError,match='Unsupported locale'):
        resolver(db)(owner,session,turn)

def test_client_does_not_supply_text(store):
    db,(owner,_,_,session,turn)=store
    snap=resolver(db)(owner,session,turn)
    assert snap.text==db.get(Turn,turn).learner_text
