"""Step 5.4b.7: HTTP + ownership + durable ledger, no external provider calls."""
import json
import sys
from types import ModuleType
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import ForeignKey, String, Uuid, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.conversation_assessment_auth import VerifiedIdentity
from app.api.conversation_assessment_persistent import (
    install_persistent_assessment_endpoint, PersistentAssessmentSetupError,
)
from app.services.persistent_assessment_idempotency import AssessmentExecution, AssessmentLedgerBase
from app.services.conversational_evidence import DIMENSIONS


from tests.support.assessment_models import (
    Base, LanguageVariant, LanguageProfile, PracticeSession, ConversationTurn,
)

@pytest.fixture
def system(monkeypatch):
    model_module = ModuleType('app.models')
    for model in (LanguageVariant, LanguageProfile, PracticeSession, ConversationTurn):
        setattr(model_module, model.__name__, model)
    monkeypatch.setitem(sys.modules, 'app.models', model_module)
    engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    AssessmentLedgerBase.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    users = {'a': uuid4(), 'b': uuid4()}
    ids = {}
    with factory() as db:
        db.add(LanguageVariant(id=1, code='fr-CA'))
        for name in users:
            profile_id, session_id, turn_id, request_id = [uuid4() for _ in range(4)]
            db.add(LanguageProfile(id=profile_id, user_id=users[name], language_variant_id=1))
            db.add(PracticeSession(id=session_id, language_profile_id=profile_id, scenario_key='Executive update'))
            db.add(ConversationTurn(id=turn_id, practice_session_id=session_id,
                client_request_id=request_id, input_modality='voice' if name == 'a' else 'text',
                learner_text='Je recommande une approche progressive pour notre projet.'))
            ids[name] = session_id, turn_id, request_id
        db.commit()
    calls = []
    def model_call(request):
        calls.append(request)
        payload=json.loads(request.user_payload)
        return {'observations': [
            {'dimension': dimension, 'status': 'MODEL_JUDGMENT' if dimension == 'clarity' else 'NOT_ASSESSED',
             'explanation':'Clear statement.' if dimension == 'clarity' else 'No evidence.',
             'supporting_quote': 'approche progressive' if dimension == 'clarity' else None}
            for dimension in DIMENSIONS]}
    def verify(token):
        if token in users: return VerifiedIdentity(users[token], True, frozenset({'conversation:assess'}))
        raise ValueError('invalid')
    def session_dependency():
        with factory() as db: yield db
    app=FastAPI()
    assert install_persistent_assessment_endpoint(app, enabled=True,
       verify_bearer_token=verify, context_from_session=lambda session: 'professional',
       model_call=model_call, session_dependency=session_dependency, ledger_session_factory=factory)
    with TestClient(app) as client:
        yield client, ids, calls, factory, users, app
    engine.dispose()

def request(client, ids, owner='a', token='a', *, request_id=None):
    session, turn, req = ids[owner]
    return client.post(f'/practice-sessions/{session}/turns/{turn}/assessment',
        headers={'Authorization':f'Bearer {token}'},
        json={'client_request_id':str(request_id or req)})

def test_first_execution_persists_and_second_replays(system):
    client, ids, calls, factory, *_ = system
    one = request(client, ids)
    two = request(client, ids)
    assert one.status_code == two.status_code == 200, (one.text, two.text)
    assert one.json()['execution_status'] == 'EXECUTED'
    assert two.json()['execution_status'] == 'REPLAYED'
    assert one.json()['execution_id'] == two.json()['execution_id']
    assert len(calls) == 1
    assert one.json()['assessment']['text_origin'] == 'VOICE_TEXT_UNKNOWN'
    with factory() as db:
        assert db.execute(select(AssessmentExecution)).scalar_one().status == 'COMPLETED'

def test_other_user_cannot_get_replayed_result(system):
    client, ids, calls, *_ = system
    assert request(client, ids).status_code == 200
    forbidden = request(client, ids, token='b')
    assert forbidden.status_code == 404
    assert len(calls) == 1

def test_other_user_cannot_initialize_foreign_ledger(system):
    client, ids, calls, factory, *_ = system
    assert request(client, ids, token='b').status_code == 404
    assert calls == []
    with factory() as db:
        assert db.execute(select(AssessmentExecution)).all() == []

def test_wrong_committed_request_id_does_not_claim(system):
    client, ids, calls, factory, *_ = system
    assert request(client, ids, request_id=uuid4()).status_code == 404
    with factory() as db: assert db.execute(select(AssessmentExecution)).all() == []

def test_missing_token_rejected(system):
    client, ids, calls, *_ = system
    session,turn,req=ids['a']
    response=client.post(f'/practice-sessions/{session}/turns/{turn}/assessment', json={'client_request_id':str(req)})
    assert response.status_code == 401 and not calls

def test_existing_processing_and_failed_never_dispatch(system):
    client, ids, calls, factory, *_ = system
    assert request(client, ids).status_code == 200
    with factory() as db:
        row=db.execute(select(AssessmentExecution)).scalar_one()
        row.status='PROCESSING'; row.result_json=None; db.commit()
    assert request(client, ids).status_code == 409
    with factory() as db:
        row=db.execute(select(AssessmentExecution)).scalar_one()
        row.status='FAILED'; db.commit()
    assert request(client, ids).status_code == 409
    assert len(calls)==1

def test_evidence_changed_is_conflict_and_no_reexecution(system):
    client, ids, calls, factory, *_ = system
    assert request(client, ids).status_code == 200
    with factory() as db:
        db.get(ConversationTurn, ids['a'][1]).learner_text='Nouvelle phrase modifiée.'
        db.commit()
    assert request(client, ids).status_code == 409
    assert len(calls)==1

def test_enabled_requires_all_dependencies():
    app=FastAPI()
    assert install_persistent_assessment_endpoint(app,enabled=False) is False
    with pytest.raises(PersistentAssessmentSetupError):
        install_persistent_assessment_endpoint(app, enabled=True)
    assert not app.routes or all('assessment' not in getattr(r,'path','') for r in app.routes)

def test_duplicate_registration_rejected(system):
    client, ids, calls, factory, users, app=system
    with pytest.raises(PersistentAssessmentSetupError):
        install_persistent_assessment_endpoint(app,enabled=True,
            verify_bearer_token=lambda t: VerifiedIdentity(users['a'],True,frozenset({'conversation:assess'})),
            context_from_session=lambda s:'professional',model_call=lambda r:{},
            session_dependency=lambda:None,ledger_session_factory=factory)
