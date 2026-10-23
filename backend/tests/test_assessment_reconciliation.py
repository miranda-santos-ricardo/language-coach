from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.services.persistent_assessment_idempotency import (
    AssessmentExecution, AssessmentLedgerBase, AssessmentBusy, PersistentAssessmentLedger,
)
from app.services.assessment_reconciliation import (
    AssessmentReconciliationEvent, ReconciliationDenied, reconcile_as_failed,
)


@pytest.fixture
def setup(tmp_path):
    engine = create_engine(f'sqlite+pysqlite:///{tmp_path / "ledger.db"}')
    AssessmentLedgerBase.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    ids = [uuid4() for _ in range(4)]
    ledger = PersistentAssessmentLedger(factory)
    args = dict(user_id=ids[0], practice_session_id=ids[1], turn_id=ids[2],
                client_request_id=ids[3], evaluator_version='v1', fingerprint=sha256(b'text').hexdigest())
    yield factory, ledger, args
    engine.dispose()


def processing_record(factory, args):
    from datetime import datetime, timezone
    from uuid import uuid4
    row = AssessmentExecution(id=uuid4(), **args, status='PROCESSING', result_json=None,
                              attempt_count=1, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    with factory.begin() as db:
        db.add(row)
    return row.id


def test_privileged_reconciliation_records_audit_and_blocks_reexecution(setup):
    factory, ledger, args = setup
    execution_id = processing_record(factory, args)
    operator_id = uuid4()
    with factory.begin() as db:
        outcome = reconcile_as_failed(db, execution_id=execution_id, operator_id=operator_id,
                                      authorized=True, reason_code='WORKER_TERMINATED', ticket_reference='INC-417')
    calls = []
    with pytest.raises(AssessmentBusy):
        ledger.execute(**args, evaluate=lambda: calls.append(1) or {})
    assert calls == []
    with factory() as db:
        row = db.get(AssessmentExecution, execution_id)
        event = db.execute(select(AssessmentReconciliationEvent)).scalar_one()
        assert row.status == outcome.status == 'FAILED'
        assert event.operator_id == operator_id
        assert event.ticket_reference == 'INC-417'
        assert event.previous_status == 'PROCESSING'
        assert event.new_status == 'FAILED'


def test_unauthorized_operator_cannot_change_record(setup):
    factory, _, args = setup
    execution_id = processing_record(factory, args)
    with factory.begin() as db:
        with pytest.raises(ReconciliationDenied):
            reconcile_as_failed(db, execution_id=execution_id, operator_id=uuid4(),
                                authorized=False, reason_code='WORKER_TERMINATED', ticket_reference='INC-1')
    with factory() as db:
        assert db.get(AssessmentExecution, execution_id).status == 'PROCESSING'


def test_completed_assessment_cannot_be_reconciled(setup):
    factory, ledger, args = setup
    outcome = ledger.execute(**args, evaluate=lambda: {'ok': True})
    with factory.begin() as db:
        with pytest.raises(ReconciliationDenied):
            reconcile_as_failed(db, execution_id=outcome.execution_id, operator_id=uuid4(),
                                authorized=True, reason_code='WORKER_TERMINATED', ticket_reference='INC-1')
    with factory() as db:
        assert db.get(AssessmentExecution, outcome.execution_id).status == 'COMPLETED'


def test_second_reconciliation_rejected_and_single_event(setup):
    factory, _, args = setup
    execution_id = processing_record(factory, args)
    for i in range(2):
        with factory.begin() as db:
            if i == 0:
                reconcile_as_failed(db, execution_id=execution_id, operator_id=uuid4(), authorized=True,
                                    reason_code='UNKNOWN_PROVIDER_OUTCOME', ticket_reference='INC-2')
            else:
                with pytest.raises(ReconciliationDenied):
                    reconcile_as_failed(db, execution_id=execution_id, operator_id=uuid4(), authorized=True,
                                        reason_code='UNKNOWN_PROVIDER_OUTCOME', ticket_reference='INC-2')
    with factory() as db:
        assert len(db.execute(select(AssessmentReconciliationEvent)).scalars().all()) == 1


@pytest.mark.parametrize('reason,ticket', [('', 'INC'), ('abc', ''), ('contains spaces','INC'), ('X'*61, 'INC')])
def test_bad_audit_metadata_rejected(setup, reason, ticket):
    factory, _, args = setup
    execution_id = processing_record(factory, args)
    with factory.begin() as db:
        with pytest.raises(ReconciliationDenied):
            reconcile_as_failed(db, execution_id=execution_id, operator_id=uuid4(), authorized=True,
                                reason_code=reason, ticket_reference=ticket)
