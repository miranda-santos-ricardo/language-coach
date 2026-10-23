from dataclasses import replace
from uuid import uuid4
import json
import pytest

from app.services.conversation_turn_assessment import (
    CommittedTurnSnapshot, ConversationTurnAssessmentService, TurnAssessmentError,
)
from app.services.conversational_evidence import DIMENSIONS
from app.services.controlled_conversational_evaluator import EvaluatorFailure


def setup_case(**changes):
    ids = [uuid4() for _ in range(4)]
    turn = CommittedTurnSnapshot(*ids, 'fr-CA', 'professional',
        'Explain the project risks to leadership',
        'We identified three risks and recommend careful monitoring.',
        'TYPED', False, True, True)
    turn = replace(turn, **changes)
    calls = []
    def provider(request):
        calls.append(request)
        return json.dumps({'observations': [
            {'dimension': d, 'status':'NOT_ASSESSED',
             'explanation':'Insufficient context for validated judgment.',
             'supporting_quote': None} for d in DIMENSIONS
        ]})
    def resolver(u, s, t):
        return turn
    service = ConversationTurnAssessmentService(resolve_turn=resolver, model_call=provider)
    opts = dict(authenticated_user_id=ids[0], practice_session_id=ids[1],
                conversation_turn_id=ids[2], client_request_id=ids[3],
                scenario_type='executive_update', evaluator_version='model-v1')
    return service, opts, calls, turn, provider


def test_success_and_provenance():
    service, opts, calls, turn, _ = setup_case()
    res = service.assess(**opts)
    assert res.assessment.locale == 'fr-CA'
    assert len(res.text_sha256) == 64
    assert res.turn_id == turn.conversation_turn_id
    assert len(calls) == 1
    assert 'submitted_text' in calls[0].user_payload


def test_retry_returns_same_result_without_model_recall():
    service, opts, calls, _, _ = setup_case()
    assert service.assess(**opts) is service.assess(**opts)
    assert len(calls) == 1


@pytest.mark.parametrize('field', [
    'user_id','practice_session_id','conversation_turn_id','client_request_id',
])
def test_identity_mismatch_fails_closed(field):
    service, opts, calls, _, _ = setup_case(**{field:uuid4()})
    with pytest.raises(TurnAssessmentError):
        service.assess(**opts)
    assert not calls


@pytest.mark.parametrize('changes', [{'committed':False},{'learner_turn':False},
                                      {'committed':1},{'learner_turn':1}])
def test_state_rejected(changes):
    service, opts, calls, _, _ = setup_case(**changes)
    with pytest.raises(TurnAssessmentError):
        service.assess(**opts)
    assert not calls


def test_conflict_on_changed_text():
    service, opts, calls, turn, provider = setup_case()
    service.assess(**opts)
    service._resolve_turn = lambda *_: replace(turn,text=turn.text+' More detail.')
    with pytest.raises(TurnAssessmentError,match='Idempotency conflict'):
        service.assess(**opts)
    assert len(calls) == 1


@pytest.mark.parametrize('field,value', [
    ('scenario_type','general'), ('evaluator_version','model-v2'),
])
def test_conflict_on_changed_configuration(field,value):
    service, opts, calls, _, _ = setup_case()
    service.assess(**opts)
    with pytest.raises(TurnAssessmentError,match='Idempotency conflict'):
        service.assess(**{**opts,field:value})
    assert len(calls) == 1


def test_failures_retry_without_cache():
    service, opts, calls, _, provider = setup_case()
    attempts = [0]
    def flaky(req):
        attempts[0]+=1
        if attempts[0]==1: raise RuntimeError('secret data')
        return provider(req)
    service._model_call = flaky
    with pytest.raises(EvaluatorFailure,match='Model provider failed') as exc:
        service.assess(**opts)
    assert 'secret' not in str(exc.value)
    service.assess(**opts)
    assert attempts[0] == 2


def test_insufficient_skips_provider():
    service, opts, calls, _, _ = setup_case(text='Too short')
    res=service.assess(**opts)
    assert res.assessment.status=='INSUFFICIENT_EVIDENCE'
    assert calls == []


@pytest.mark.parametrize('origin,stt', [('STT_UNEDITED',True),('USER_EDITED',False),('TYPED',False)])
def test_provenance_preserved(origin, stt):
    service, opts, calls, _, _ = setup_case(origin=origin,stt_original_available=stt)
    res=service.assess(**opts)
    assert res.assessment.text_origin==origin
    assert len(calls)==1


def test_unedited_stt_requires_provenance():
    service, opts, calls, _, _ = setup_case(origin='STT_UNEDITED',stt_original_available=False)
    with pytest.raises(TurnAssessmentError): service.assess(**opts)
    assert calls == []


def test_resolution_failure_sanitized():
    service, opts, calls, _, _ = setup_case()
    def forbidden(*_): raise RuntimeError('sensitive path or identity')
    service._resolve_turn=forbidden
    with pytest.raises(TurnAssessmentError, match='Turn resolution or authorization failed') as exc:
        service.assess(**opts)
    assert 'sensitive' not in str(exc.value)
    assert not calls


@pytest.mark.parametrize('field', ['authenticated_user_id','practice_session_id','conversation_turn_id','client_request_id'])
def test_invalid_caller_ids(field):
    service, opts, calls, _, _ = setup_case()
    with pytest.raises(TurnAssessmentError): service.assess(**{**opts,field:'fake'})
    assert calls == []


def test_different_request_id_cannot_alias_committed_turn():
    service, opts, calls, _, _=setup_case()
    with pytest.raises(TurnAssessmentError):
        service.assess(**{**opts,'client_request_id':uuid4()})
    assert not calls


def test_no_client_text_argument():
    service, opts, calls, _, _=setup_case()
    with pytest.raises(TypeError): service.assess(**{**opts,'text':'injected'})
    assert not calls


def test_invalid_resolver_type():
    service, opts, calls, _, _=setup_case()
    service._resolve_turn=lambda *_: {'user_id':opts['authenticated_user_id']}
    with pytest.raises(TurnAssessmentError): service.assess(**opts)
    assert not calls


def test_sequential_caching_is_per_instance_only():
    service, opts, calls, turn, provider=setup_case()
    service.assess(**opts)
    other=ConversationTurnAssessmentService(resolve_turn=lambda *_:turn,model_call=provider)
    other.assess(**opts)
    assert len(calls)==2
