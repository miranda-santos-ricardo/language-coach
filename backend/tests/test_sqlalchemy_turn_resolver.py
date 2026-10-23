"""SQLite integration tests exercise the actual SQL joins and owner filters."""
from uuid import uuid4
import pytest
from sqlalchemy import ForeignKey, String, Uuid, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from app.services.sqlalchemy_turn_resolver import make_sqlalchemy_turn_resolver
from app.services.conversation_turn_assessment import TurnAssessmentError

class Base(DeclarativeBase): pass
class Profile(Base):
    __tablename__='language_profiles'
    id:Mapped[object]=mapped_column(Uuid(as_uuid=True),primary_key=True)
    user_id:Mapped[object]=mapped_column(Uuid(as_uuid=True))
    language_variant_id:Mapped[int]=mapped_column(ForeignKey('language_variants.id'))
class Variant(Base):
    __tablename__='language_variants'
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String)
class Practice(Base):
    __tablename__='practice_sessions'
    id:Mapped[object]=mapped_column(Uuid(as_uuid=True),primary_key=True)
    language_profile_id:Mapped[object]=mapped_column(ForeignKey('language_profiles.id'))
    scenario_key:Mapped[str | None]=mapped_column(String,nullable=True)
class Turn(Base):
    __tablename__='conversation_turns'
    id:Mapped[object]=mapped_column(Uuid(as_uuid=True),primary_key=True)
    practice_session_id:Mapped[object]=mapped_column(ForeignKey('practice_sessions.id'))
    client_request_id:Mapped[object]=mapped_column(Uuid(as_uuid=True))
    input_modality:Mapped[str]=mapped_column(String)
    learner_text:Mapped[str]=mapped_column(String)

@pytest.fixture
def store():
    engine=create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        ids=[uuid4() for _ in range(5)]
        owner,other,profile,session,turn=ids
        db.add_all([Variant(id=1,code='fr-CA'), Profile(id=profile,user_id=owner,language_variant_id=1),
                    Practice(id=session,language_profile_id=profile,scenario_key='Executive update'),
                    Turn(id=turn,practice_session_id=session,client_request_id=uuid4(),
                         input_modality='text',learner_text='Voici les prochaines étapes du projet.')])
        db.commit()
        yield db,ids
    engine.dispose()

def resolver(db,**kwargs):
    return make_sqlalchemy_turn_resolver(db,context_from_session=lambda _: 'professional',
                                        models=(Turn,Practice,Profile,Variant),**kwargs)

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
