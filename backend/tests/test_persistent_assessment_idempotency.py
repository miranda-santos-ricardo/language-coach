from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.persistent_assessment_idempotency import (
    AssessmentLedgerBase, AssessmentExecution, PersistentAssessmentLedger,
    AssessmentBusy, AssessmentConflict, evidence_fingerprint,
)


@pytest.fixture
def environment():
    engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    AssessmentLedgerBase.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    ids = [uuid4() for _ in range(4)]
    fingerprint = sha256(b'committed evidence').hexdigest()
    yield factory, ids, fingerprint
    engine.dispose()


def request(ledger, ids, fingerprint, evaluator_version='rubric-v1', evaluate=lambda: {'assessment': {'status': 'REVIEWED'}}):
    return ledger.execute(user_id=ids[0], practice_session_id=ids[1], turn_id=ids[2],
                          client_request_id=ids[3], evaluator_version=evaluator_version,
                          fingerprint=fingerprint, evaluate=evaluate)


def test_completed_result_replays_between_independent_service_instances(environment):
    factory, ids, fingerprint = environment
    a, b = PersistentAssessmentLedger(factory), PersistentAssessmentLedger(factory)
    calls = []
    one = request(a, ids, fingerprint, evaluate=lambda: calls.append(1) or {'assessment': {'status': 'REVIEWED'}})
    two = request(b, ids, fingerprint, evaluate=lambda: calls.append(2) or {})
    assert one.status == 'EXECUTED'
    assert two.status == 'REPLAYED'
    assert one.execution_id == two.execution_id
    assert calls == [1]


def test_changed_committed_evidence_rejected(environment):
    factory, ids, fingerprint = environment
    ledger = PersistentAssessmentLedger(factory)
    request(ledger, ids, fingerprint)
    with pytest.raises(AssessmentConflict):
        request(ledger, ids, sha256(b'new evidence').hexdigest())


def test_running_claim_blocks_second_worker(environment):
    factory, ids, fingerprint = environment
    entered, release = Event(), Event()
    ledger1, ledger2 = PersistentAssessmentLedger(factory), PersistentAssessmentLedger(factory)
    def slow():
        entered.set()
        assert release.wait(5)
        return {'ok': True}
    with ThreadPoolExecutor(max_workers=2) as executor:
        task = executor.submit(request, ledger1, ids, fingerprint, 'rubric-v1', slow)
        assert entered.wait(5)
        with pytest.raises(AssessmentBusy):
            request(ledger2, ids, fingerprint, evaluate=lambda: {'bad': 'double dispatch'})
        release.set()
        assert task.result(timeout=5).status == 'EXECUTED'


def test_failed_provider_never_auto_retries(environment):
    factory, ids, fingerprint = environment
    ledger = PersistentAssessmentLedger(factory)
    calls = []
    def fail():
        calls.append(1)
        raise RuntimeError('Provider failed')
    with pytest.raises(RuntimeError):
        request(ledger, ids, fingerprint, evaluate=fail)
    with pytest.raises(AssessmentBusy):
        request(ledger, ids, fingerprint, evaluate=fail)
    assert calls == [1]
    with factory() as db:
        row = db.execute(select(AssessmentExecution)).scalar_one()
        assert row.status == 'FAILED'
        assert row.result_json is None


def test_version_is_part_of_unique_key(environment):
    factory, ids, fingerprint = environment
    ledger = PersistentAssessmentLedger(factory)
    a = request(ledger, ids, fingerprint, 'v1')
    b = request(ledger, ids, fingerprint, 'v2')
    assert a.execution_id != b.execution_id


def test_different_users_cannot_share_assessment_cache(environment):
    factory, ids, fingerprint = environment
    ledger = PersistentAssessmentLedger(factory)
    result = request(ledger, ids, fingerprint)
    other = [uuid4(), *ids[1:]]
    assert request(ledger, other, fingerprint).execution_id != result.execution_id


def test_no_plaintext_or_token_stored_in_audit_row(environment):
    factory, ids, fingerprint = environment
    ledger = PersistentAssessmentLedger(factory)
    request(ledger, ids, fingerprint, evaluate=lambda: {'status':'REVIEWED'})
    with factory() as db:
        row = db.execute(select(AssessmentExecution)).scalar_one()
        assert row.fingerprint == fingerprint and row.result_json == {'status':'REVIEWED'}
        assert not hasattr(row, 'bearer_token') and not hasattr(row, 'prompt')


def test_fingerprint_sensitive_to_provenance_and_model_version():
    fields = dict(text='Bonjour tout le monde', locale='fr-CA', context='professional',
                  scenario='general', origin='VOICE_TEXT_UNKNOWN', scenario_type='general',
                  evaluator_version='v1', stt_original_available=False)
    digest = evidence_fingerprint(**fields)
    assert len(digest) == 64
    assert digest != evidence_fingerprint(**{**fields, 'origin':'USER_EDITED'})
    assert digest != evidence_fingerprint(**{**fields, 'evaluator_version':'v2'})
    assert digest != evidence_fingerprint(**{**fields, 'text':'Other text'})


def test_rejects_invalid_keys_before_provider(environment):
    factory, ids, fingerprint = environment
    ledger = PersistentAssessmentLedger(factory)
    with pytest.raises(ValueError):
        request(ledger, ids, 'invalid')
    with pytest.raises(ValueError):
        request(ledger, ['not-uuid', *ids[1:]], fingerprint)


def test_json_non_serializable_result_marks_failed(environment):
    factory, ids, fingerprint = environment
    ledger = PersistentAssessmentLedger(factory)
    with pytest.raises(TypeError):
        request(ledger, ids, fingerprint, evaluate=lambda:{'bad': object()})
    with factory() as db:
        assert db.execute(select(AssessmentExecution)).scalar_one().status == 'FAILED'
