from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.assessment_admin_recovery import AdminRecoverySetupError, install_assessment_admin_recovery
from app.api.conversation_assessment_auth import VerifiedIdentity
from app.services.assessment_reconciliation import AssessmentReconciliationEvent
from app.services.persistent_assessment_idempotency import AssessmentExecution, AssessmentLedgerBase


@pytest.fixture
def harness(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'admin.db'}")
    AssessmentLedgerBase.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    execution_id = uuid4()
    operator = uuid4()
    now = datetime.now(timezone.utc)
    with factory.begin() as db:
        db.add(AssessmentExecution(id=execution_id, user_id=uuid4(), practice_session_id=uuid4(),
                turn_id=uuid4(), client_request_id=uuid4(), evaluator_version="v1",
                fingerprint=sha256(b"text").hexdigest(), status="PROCESSING", result_json=None,
                attempt_count=1, created_at=now, updated_at=now))
    app = FastAPI()
    def get_db():
        with factory() as db:
            yield db
    def verifier(token):
        if token == "bad":
            raise ValueError("untrusted")
        scopes = frozenset({"conversation:assessment:reconcile"}) if token == "admin" else frozenset({"conversation:assess"})
        return VerifiedIdentity(user_id=operator, active=token != "inactive", scopes=scopes)
    yield app, factory, execution_id, operator, verifier, get_db
    engine.dispose()


def install(h):
    app, _, _, _, verifier, get_db = h
    install_assessment_admin_recovery(app, enabled=True, verify_bearer_token=verifier, session_dependency=get_db)
    return TestClient(app)


def path(e):
    return f"/admin/assessments/{e}/reconcile-as-failed"


def payload():
    return {"reason_code": "WORKER_TERMINATED", "ticket_reference": "INC-123"}


def test_disabled_by_default(harness):
    app, *_ = harness
    assert install_assessment_admin_recovery(app) is False
    assert TestClient(app).post(path(uuid4()), json=payload()).status_code == 404


def test_requires_dependencies_and_disallows_double_mount(harness):
    app, _, _, _, verifier, get_db = harness
    with pytest.raises(AdminRecoverySetupError):
        install_assessment_admin_recovery(app, enabled=True)
    install(harness)
    with pytest.raises(AdminRecoverySetupError):
        install_assessment_admin_recovery(app, enabled=True, verify_bearer_token=verifier, session_dependency=get_db)


@pytest.mark.parametrize("token,expected", [(None,401), ("bad",401), ("learner",403), ("inactive",403)])
def test_auth_denied(harness, token, expected):
    client = install(harness)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    assert client.post(path(harness[2]), json=payload(), headers=headers).status_code == expected
    with harness[1]() as db:
        assert db.get(AssessmentExecution, harness[2]).status == "PROCESSING"
        assert db.execute(select(AssessmentReconciliationEvent)).scalars().all() == []


def test_success_audit_atomic_and_no_replay(harness):
    client = install(harness)
    headers = {"Authorization": "Bearer admin", "X-User-Id": str(uuid4())}
    r = client.post(path(harness[2]), json=payload(), headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "FAILED"
    with harness[1]() as db:
        assert db.get(AssessmentExecution, harness[2]).status == "FAILED"
        events = db.execute(select(AssessmentReconciliationEvent)).scalars().all()
        assert len(events) == 1
        assert events[0].operator_id == harness[3]
        assert events[0].ticket_reference == "INC-123"
    assert client.post(path(harness[2]), json=payload(), headers=headers).status_code == 409
    with harness[1]() as db:
        assert len(db.execute(select(AssessmentReconciliationEvent)).scalars().all()) == 1


def test_unknown_execution_fails_closed(harness):
    client = install(harness)
    assert client.post(path(uuid4()), json=payload(), headers={"Authorization":"Bearer admin"}).status_code == 409


def test_input_rejects_client_identity_and_invalid_metadata(harness):
    client = install(harness)
    headers = {"Authorization": "Bearer admin"}
    assert client.post(path(harness[2]), json={**payload(), "operator_id":str(uuid4())}, headers=headers).status_code == 422
    assert client.post(path(harness[2]), json={"reason_code":"bad spaces", "ticket_reference":"INC-1"}, headers=headers).status_code == 409


def test_no_malicious_token_fallback(harness):
    client = install(harness)
    assert client.post(path(harness[2]), json=payload(), headers={"X-User-Id":str(harness[3])}).status_code == 401
