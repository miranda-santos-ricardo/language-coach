from uuid import uuid4
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from app.api.conversation_assessment_auth import (
    VerifiedIdentity, AuthenticationDenied, AuthenticationSetupError,
    make_authenticated_identity_dependency, install_authenticated_assessment_endpoint,
)

P = '/auth-check'

def app_with_auth(verifier):
    app=FastAPI()
    dep=make_authenticated_identity_dependency(verifier)
    @app.get(P)
    def check(user_id=Depends(dep)):
        return {'user_id':str(user_id)}
    return app

def test_no_bearer_denied():
    assert TestClient(app_with_auth(lambda t: None)).get(P).status_code==401

def test_client_supplied_identity_headers_do_not_authenticate():
    r=TestClient(app_with_auth(lambda t: None)).get(P,headers={'X-User-Id':str(uuid4())})
    assert r.status_code==401

def test_invalid_token_denied_without_exposing_reason():
    def verify(_): raise AuthenticationDenied('sensitive implementation detail')
    r=TestClient(app_with_auth(verify)).get(P,headers={'Authorization':'Bearer forged'})
    assert r.status_code==401 and 'sensitive' not in r.text

def test_verified_identity_resolves_from_verifier_only():
    real, forged=uuid4(), uuid4()
    def verify(token):
        assert token=='valid'
        return VerifiedIdentity(real,True,frozenset({'conversation:assess'}))
    r=TestClient(app_with_auth(verify)).get(P,headers={'Authorization':'Bearer valid','X-User-Id':str(forged)})
    assert r.status_code==200 and r.json()['user_id']==str(real)

@pytest.mark.parametrize('identity',[None,uuid4(),VerifiedIdentity(uuid4(),False,frozenset({'conversation:assess'})),VerifiedIdentity(uuid4(),True,frozenset()),VerifiedIdentity('user',True,frozenset({'conversation:assess'})),VerifiedIdentity(uuid4(),True,{'conversation:assess'})])
def test_bad_identity_denied(identity):
    r=TestClient(app_with_auth(lambda _:identity)).get(P,headers={'Authorization':'Bearer any'})
    assert r.status_code==403

def test_disabled_mounts_nothing():
    app=FastAPI()
    assert install_authenticated_assessment_endpoint(app) is False
    assert all('assessment' not in r.path for r in app.routes)

def test_enable_without_verifier_fails_closed():
    app=FastAPI()
    with pytest.raises(AuthenticationSetupError):
        install_authenticated_assessment_endpoint(app,enabled=True,context_from_session=lambda x:'professional',model_call=lambda x:'{}',session_dependency=lambda:None)
    assert all('assessment' not in r.path for r in app.routes)

def test_enable_missing_other_dependencies_fails_closed():
    app=FastAPI()
    with pytest.raises(AuthenticationSetupError):
        install_authenticated_assessment_endpoint(app,enabled=True,verify_bearer_token=lambda _:VerifiedIdentity(uuid4(),True,frozenset({'conversation:assess'})))
    assert all('assessment' not in r.path for r in app.routes)

def test_string_enablement_rejected():
    with pytest.raises(AuthenticationSetupError):
        install_authenticated_assessment_endpoint(FastAPI(),enabled='true')
