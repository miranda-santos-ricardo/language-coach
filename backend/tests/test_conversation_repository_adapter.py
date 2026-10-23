from dataclasses import replace
from uuid import uuid4
import pytest
from app.services.conversation_repository_adapter import (
    AuthorizedSessionRow, PersistedLearnerTurnRow, AuthorizedConversationRepository,
)
from app.services.conversation_turn_assessment import TurnAssessmentError


def fixture():
    user, session, turn, request = (uuid4() for _ in range(4))
    s=AuthorizedSessionRow(session,user,True)
    t=PersistedLearnerTurnRow(turn,session,user,request,'fr-CA','professional','Executive update',
       'Here is my project update.','TYPED',False,True,True)
    calls=[]
    def fs(u,sid):
        calls.append(('session',u,sid)); return s
    def ft(u,sid,tid):
        calls.append(('turn',u,sid,tid)); return t
    return (user,session,turn),s,t,calls,fs,ft

def test_success():
    ids,_,t,calls,fs,ft=fixture()
    result=AuthorizedConversationRepository(fetch_session=fs,fetch_turn=ft).resolve_turn(*ids)
    assert result.text==t.text and result.client_request_id==t.client_request_id
    assert calls==[('session',ids[0],ids[1]),('turn',*ids)]

def test_no_fetch_turn_when_session_missing():
    ids,_,_,calls,_,ft=fixture()
    repo=AuthorizedConversationRepository(fetch_session=lambda *_:None,fetch_turn=ft)
    with pytest.raises(TurnAssessmentError): repo.resolve_turn(*ids)
    assert calls==[]

@pytest.mark.parametrize('field', ['id','user_id','is_accessible'])
def test_bad_session_denied(field):
    ids,s,t,_,fs,ft=fixture()
    bad=replace(s,**{field:False if field=='is_accessible' else uuid4()})
    repo=AuthorizedConversationRepository(fetch_session=lambda *_:bad,fetch_turn=ft)
    with pytest.raises(TurnAssessmentError):repo.resolve_turn(*ids)

@pytest.mark.parametrize('field', ['id','user_id','practice_session_id','committed','learner_turn',
                                   'client_request_id','text','stt_original_available'])
def test_bad_turn_denied(field):
    ids,s,t,_,fs,ft=fixture()
    replacement={'committed':False,'learner_turn':False,'text':' ',
                 'stt_original_available':1, 'client_request_id':'not-a-uuid'}.get(field,uuid4())
    bad=replace(t,**{field:replacement})
    repo=AuthorizedConversationRepository(fetch_session=fs,fetch_turn=lambda *_:bad)
    with pytest.raises(TurnAssessmentError):repo.resolve_turn(*ids)

def test_unexpected_repository_exception_safe():
    ids,_,_,_,_,_=fixture()
    def explode(*_):raise RuntimeError('PRIVATE LEARNER DATA')
    with pytest.raises(TurnAssessmentError,match='Authorized repository lookup failed') as e:
        AuthorizedConversationRepository(fetch_session=explode,fetch_turn=explode).resolve_turn(*ids)
    assert 'PRIVATE' not in str(e.value)

@pytest.mark.parametrize('index', [0,1,2])
def test_invalid_uuid(index):
    ids,_,_,_,fs,ft=fixture(); args=list(ids);args[index]='not-a-uuid'
    with pytest.raises(TurnAssessmentError):AuthorizedConversationRepository(fetch_session=fs,fetch_turn=ft).resolve_turn(*args)

def test_bad_repository_functions():
    with pytest.raises(TurnAssessmentError):AuthorizedConversationRepository(fetch_session=None,fetch_turn=None)
