"""Shared deterministic SQL resolver fixtures; never part of application runtime."""
from uuid import uuid4
import pytest
from sqlalchemy import ForeignKey, String, Uuid, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from app.services.sqlalchemy_turn_resolver import make_sqlalchemy_turn_resolver

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

