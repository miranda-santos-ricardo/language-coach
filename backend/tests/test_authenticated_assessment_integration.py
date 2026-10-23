"""Step 5.4b.5: end-to-end HTTP + identity dependency + SQL ownership + evaluator.

SQLite model doubles preserve the join topology of production. The token verifier
and evaluator are controlled test doubles, NOT live security/LLM integrations.
"""
from __future__ import annotations

import json
import sys
from types import ModuleType
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import ForeignKey, String, Uuid, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

from app.api.conversation_assessment_auth import (
    VerifiedIdentity, install_authenticated_assessment_endpoint,
)
from app.services.conversational_evidence import DIMENSIONS


class Base(DeclarativeBase):
    pass


class LanguageVariant(Base):
    __tablename__ = 'language_variants'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String)


class LanguageProfile(Base):
    __tablename__ = 'language_profiles'
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), nullable=False)
    language_variant_id: Mapped[int] = mapped_column(ForeignKey('language_variants.id'))


class PracticeSession(Base):
    __tablename__ = 'practice_sessions'
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    language_profile_id: Mapped[object] = mapped_column(ForeignKey('language_profiles.id'))
    scenario_key: Mapped[str | None] = mapped_column(String, nullable=True)


class ConversationTurn(Base):
    __tablename__ = 'conversation_turns'
    id: Mapped[object] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    practice_session_id: Mapped[object] = mapped_column(ForeignKey('practice_sessions.id'))
    client_request_id: Mapped[object] = mapped_column(Uuid(as_uuid=True))
    input_modality: Mapped[str] = mapped_column(String)
    learner_text: Mapped[str] = mapped_column(String)


@pytest.fixture
def env(monkeypatch):
    # The production resolver imports actual app.models. Patch only that import
    # to exercise the exact SQL expression against isolated equivalent tables.
    model_module = ModuleType('app.models')
    for model in (LanguageVariant, LanguageProfile, PracticeSession, ConversationTurn):
        setattr(model_module, model.__name__, model)
    monkeypatch.setitem(sys.modules, 'app.models', model_module)

    engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    owner, stranger = uuid4(), uuid4()
    ids = {}
    with Session(engine) as db:
        db.add(LanguageVariant(id=1, code='fr-CA'))
        for name, user, modality in [('owner',owner,'voice'),('stranger',stranger,'text')]:
            profile_id, session_id, turn_id, request_id = (uuid4() for _ in range(4))
            text = 'Je recommande une approche progressive pour notre projet.' if name=='owner' else 'The private numbers belong to someone else.'
            db.add(LanguageProfile(id=profile_id,user_id=user,language_variant_id=1))
            db.add(PracticeSession(id=session_id,language_profile_id=profile_id,scenario_key='Executive update'))
            db.add(ConversationTurn(id=turn_id,practice_session_id=session_id,client_request_id=request_id,input_modality=modality,learner_text=text))
            ids[name] = (session_id,turn_id,request_id,text)
        db.commit()

    provider_calls = []
    def model_call(request):
        payload=json.loads(request.user_payload)
        provider_calls.append(payload)
        # Deterministic evidence-backed output; no outside API usage.
        return {'observations': [
            {'dimension': dimension, 'status':'MODEL_JUDGMENT' if dimension=='clarity' else 'NOT_ASSESSED',
             'explanation':'Text is understandable.' if dimension=='clarity' else 'No evidence supplied.',
             'supporting_quote': 'approche progressive' if dimension=='clarity' and 'approche progressive' in payload['submitted_text'] else ('private numbers' if dimension=='clarity' else None)}
            for dimension in DIMENSIONS
        ]}

    def verify(token):
        if token == 'owner-valid':
            return VerifiedIdentity(owner, True, frozenset({'conversation:assess'}))
        if token == 'stranger-valid':
            return VerifiedIdentity(stranger, True, frozenset({'conversation:assess'}))
        if token == 'missing-scope':
            return VerifiedIdentity(owner, True, frozenset())
        raise ValueError('sensitive invalid token reason')

    def session_dependency():
        with Session(engine) as db:
            yield db

    app=FastAPI()
    assert install_authenticated_assessment_endpoint(
        app, enabled=True, verify_bearer_token=verify,
        context_from_session=lambda session:'professional',
        model_call=model_call, session_dependency=session_dependency,
    ) is True
    with TestClient(app) as client:
        yield client, ids, provider_calls, engine, owner, stranger
    engine.dispose()


def call(client, ids, which='owner', token='owner-valid', *, request_id=None, extra=None, session=None, turn=None):
    session_id, turn_id, client_id, _ = ids[which]
    headers={} if token is None else {'Authorization': f'Bearer {token}'}
    body={'client_request_id':str(client_id if request_id is None else request_id)}
    if extra:body.update(extra)
    return client.post(f'/practice-sessions/{session or session_id}/turns/{turn or turn_id}/assessment', headers=headers,json=body)


def test_own_committed_voice_turn_is_evaluated_text_only(env):
    client, ids, calls, *_ = env
    response=call(client,ids)
    assert response.status_code==200,response.text
    data=response.json()
    assert data['assessment']['text_origin']=='VOICE_TEXT_UNKNOWN'
    assert data['assessment']['status']=='REVIEWED'
    assert data['assessment']['dimensions'][3]['status']=='MODEL_JUDGMENT'
    assert calls[0]['submitted_text']==ids['owner'][3]
    assert calls[0]['text_origin']=='VOICE_TEXT_UNKNOWN'
    assert 'audio' not in data and ids['owner'][3] not in response.text


def test_stranger_cannot_read_owner_even_knowing_all_ids(env):
    client,ids,calls,*_=env
    response=call(client,ids,token='stranger-valid')
    assert response.status_code==404
    assert response.json()=={'detail':'Assessment unavailable'}
    assert calls==[]


def test_owner_cannot_read_stranger_even_knowing_all_ids(env):
    client,ids,calls,*_=env
    response=call(client,ids,which='stranger',token='owner-valid')
    assert response.status_code==404
    assert calls==[]


def test_unknown_turn_same_error_as_cross_owner(env):
    client,ids,calls,*_=env
    r=call(client,ids,turn=uuid4())
    assert r.status_code==404 and r.json()=={'detail':'Assessment unavailable'}
    assert calls==[]


def test_wrong_session_denied_by_sql_owner_join(env):
    client,ids,calls,*_=env
    r=call(client,ids,session=ids['stranger'][0])
    assert r.status_code==404 and calls==[]


def test_wrong_committed_client_request_denied(env):
    client,ids,calls,*_=env
    r=call(client,ids,request_id=uuid4())
    assert r.status_code==404 and calls==[]


def test_missing_or_invalid_bearer_rejected_without_evaluation(env):
    client,ids,calls,*_=env
    for token in [None,'forged']:
        r=call(client,ids,token=token)
        assert r.status_code==401
        assert 'sensitive' not in r.text
    assert calls==[]


def test_scope_missing_forbidden(env):
    client,ids,calls,*_=env
    assert call(client,ids,token='missing-scope').status_code==403
    assert calls==[]


def test_cannot_spoof_user_id_or_replace_text(env):
    client,ids,calls,*_=env
    for extra in [{'user_id':str(uuid4())},{'text':'Forged content'},{'input_modality':'text'}]:
        r=call(client,ids,extra=extra)
        assert r.status_code==422
    assert calls==[]


def test_model_failure_safe_and_not_cached(env):
    client,ids,calls,engine,*_=env
    # Temporarily change committed text so model evidence is too weak; this
    # tests the evidence gate rather than external-provider failures.
    with Session(engine) as db:
        db.get(ConversationTurn,ids['owner'][1]).learner_text='Bonjour'
        db.commit()
    response=call(client,ids)
    assert response.status_code==200
    assert response.json()['assessment']['status']=='INSUFFICIENT_EVIDENCE'
    assert calls==[]


def test_verified_header_never_overrides_bearer_identity(env):
    client, ids, calls, *rest = env
    session_id,turn_id,client_id,_=ids['owner']
    r=client.post(f'/practice-sessions/{session_id}/turns/{turn_id}/assessment',
                  headers={'Authorization':'Bearer stranger-valid','X-User-Id':str(rest[1])},
                  json={'client_request_id':str(client_id)})
    assert r.status_code==404 and calls==[]


def test_malformed_provider_result_returns_safe_404(env):
    client,ids,calls,engine,*_=env
    # Force model's fixed quote to be absent from persisted text.
    with Session(engine) as db:
        db.get(ConversationTurn,ids['stranger'][1]).learner_text='This sentence contains no expected quotation.'
        db.commit()
    r=call(client,ids,which='stranger',token='stranger-valid')
    assert r.status_code==404
    assert r.json()=={'detail':'Assessment unavailable'}
    assert len(calls)==1
    assert ids['stranger'][3] not in r.text


def test_repeat_requests_not_durable_idempotent(env):
    client,ids,calls,*_=env
    one=call(client,ids)
    two=call(client,ids)
    assert one.status_code==200 and two.status_code==200
    assert one.json()['text_sha256']==two.json()['text_sha256']
    # Current wiring allocates one service per request: no cross-request cache.
    # Deliberately document this hazard rather than incorrectly claim once-only.
    assert len(calls)==2


def test_disabled_flag_keeps_route_unmounted():
    app=FastAPI()
    assert install_authenticated_assessment_endpoint(app,enabled=False) is False
    r=TestClient(app).post(f'/practice-sessions/{uuid4()}/turns/{uuid4()}/assessment',
                            json={'client_request_id':str(uuid4())})
    assert r.status_code==404
