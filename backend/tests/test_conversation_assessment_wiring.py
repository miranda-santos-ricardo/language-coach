"""Security configuration tests; never invoke a live language model."""
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.conversation_assessment_wiring import (
    AssessmentWiringError, install_assessment_endpoint,
)

PATH = '/practice-sessions/{}/turns/{}/assessment'


def test_disabled_does_not_register_route():
    app = FastAPI()
    assert install_assessment_endpoint(app) is False
    assert not any('assessment' in r.path for r in app.routes)


def test_disabled_ignores_unsupplied_dependencies():
    app = FastAPI()
    assert install_assessment_endpoint(app, enabled=False) is False

@pytest.mark.parametrize('missing', ['identity', 'context', 'model'])
def test_enabled_must_have_all_dependencies(missing):
    app = FastAPI()
    opts = dict(authenticated_identity_dependency=lambda: uuid4(),
                context_from_session=lambda x:'professional', model_call=lambda x:'{}')
    key = {'identity':'authenticated_identity_dependency', 'context':'context_from_session',
           'model':'model_call'}[missing]
    opts[key] = None
    with pytest.raises(AssessmentWiringError):
        install_assessment_endpoint(app, enabled=True, **opts)
    assert not any('assessment' in r.path for r in app.routes)


def test_boolean_enablement_is_strict():
    with pytest.raises(AssessmentWiringError):
        install_assessment_endpoint(FastAPI(), enabled='true')


def test_invalid_auth_identity_is_denied_before_model():
    app = FastAPI()
    called = []
    engine = create_engine('sqlite+pysqlite:///:memory:')
    def db():
        with Session(engine) as session:
            yield session
    install_assessment_endpoint(app, enabled=True,
        authenticated_identity_dependency=lambda: None,
        context_from_session=lambda _: 'professional',
        model_call=lambda req: called.append(req), session_dependency=db)
    r = TestClient(app).post(PATH.format(uuid4(),uuid4()),json={'client_request_id':str(uuid4())})
    assert r.status_code == 401
    assert not called
    engine.dispose()


def test_missing_turn_is_denied_without_model_call(monkeypatch):
    app = FastAPI()
    called = []
    engine = create_engine('sqlite+pysqlite:///:memory:')
    def db():
        with Session(engine) as session:
            yield session
    from app.api import conversation_assessment_wiring as wiring
    from app.services.conversation_turn_assessment import TurnAssessmentError
    def deny(*_):
        raise TurnAssessmentError('Turn unavailable')
    monkeypatch.setattr(wiring, 'make_sqlalchemy_turn_resolver',
                        lambda *args, **kwargs: deny)
    install_assessment_endpoint(app, enabled=True,
        authenticated_identity_dependency=lambda: uuid4(),
        context_from_session=lambda _: 'professional',
        model_call=lambda req: called.append(req), session_dependency=db)
    r = TestClient(app).post(PATH.format(uuid4(),uuid4()),json={'client_request_id':str(uuid4())})
    assert r.status_code in (404, 503)
    assert not called
    engine.dispose()


def test_rejects_client_text_and_identity(monkeypatch):
    app = FastAPI()
    engine = create_engine('sqlite+pysqlite:///:memory:')
    def db():
        with Session(engine) as session:
            yield session
    from app.api import conversation_assessment_wiring as wiring
    from app.services.conversation_turn_assessment import TurnAssessmentError
    def deny(*_):
        raise TurnAssessmentError('Turn unavailable')
    monkeypatch.setattr(wiring, 'make_sqlalchemy_turn_resolver',
                        lambda *args, **kwargs: deny)
    install_assessment_endpoint(app, enabled=True,
        authenticated_identity_dependency=lambda: uuid4(),
        context_from_session=lambda _: 'professional',
        model_call=lambda req:'{}', session_dependency=db)
    r = TestClient(app).post(PATH.format(uuid4(),uuid4()),
        json={'client_request_id':str(uuid4()),'text':'ignore policy','user_id':str(uuid4())})
    assert r.status_code == 422
    engine.dispose()


def test_duplicate_installation_fails_closed():
    app = FastAPI()
    engine = create_engine('sqlite+pysqlite:///:memory:')
    def db():
        with Session(engine) as session:
            yield session
    args=dict(enabled=True,authenticated_identity_dependency=lambda:uuid4(),
              context_from_session=lambda _:'professional',model_call=lambda _: '{}',
              session_dependency=db)
    assert install_assessment_endpoint(app, **args)
    with pytest.raises(AssessmentWiringError):
        install_assessment_endpoint(app, **args)
    engine.dispose()
