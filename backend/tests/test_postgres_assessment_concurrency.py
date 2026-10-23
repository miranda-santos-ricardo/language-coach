"""Optional PostgreSQL integration suite. Set ASSESSMENT_TEST_POSTGRES_URL to a disposable DB.

Example URL: postgresql+psycopg://user:password@localhost:5432/language_coach_test
Never use a production database. Database must have been migrated to c5202603.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
from hashlib import sha256

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.services.persistent_assessment_idempotency import (
    AssessmentBusy, AssessmentExecution, PersistentAssessmentLedger,
)
from app.services.assessment_reconciliation import (
    AssessmentReconciliationEvent, reconcile_as_failed,
)


@pytest.fixture
def pg():
    url = os.environ.get('ASSESSMENT_TEST_POSTGRES_URL')
    if not url:
        pytest.skip('Set ASSESSMENT_TEST_POSTGRES_URL for disposable PostgreSQL test database')
    engine = create_engine(url, pool_size=5, max_overflow=5, pool_pre_ping=True)
    # Uses a migrated database; do not create/drop real tables here.
    with engine.connect() as conn:
        assert conn.dialect.name == 'postgresql'
        for table in (AssessmentExecution.__table__, AssessmentReconciliationEvent.__table__):
            from sqlalchemy import inspect
            assert inspect(conn).has_table(table.name), f'Migrate test DB first: missing {table.name}'
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


def test_two_independent_connections_single_provider_dispatch(pg):
    a, b = PersistentAssessmentLedger(pg), PersistentAssessmentLedger(pg)
    args = dict(user_id=uuid4(), practice_session_id=uuid4(), turn_id=uuid4(),
                client_request_id=uuid4(), evaluator_version='test-'+uuid4().hex,
                fingerprint=sha256(b'committed').hexdigest())
    called, release = Event(), Event()
    executions = []
    def slow():
        executions.append('first')
        called.set()
        assert release.wait(10)
        return {'status': 'REVIEWED'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(a.execute, **args, evaluate=slow)
        try:
            assert called.wait(10)
            with pytest.raises(AssessmentBusy):
                b.execute(**args, evaluate=lambda: executions.append('duplicate') or {})
        finally:
            release.set()
        first = future.result(timeout=10)
    replay = b.execute(**args, evaluate=lambda: executions.append('replay') or {})
    assert first.status == 'EXECUTED' and replay.status == 'REPLAYED'
    assert first.execution_id == replay.execution_id
    assert executions == ['first']


def test_postgres_reconciliation_row_lock_and_audit(pg):
    execution_id = uuid4()
    args = dict(user_id=uuid4(), practice_session_id=uuid4(), turn_id=uuid4(),
                client_request_id=uuid4(), evaluator_version='test-'+uuid4().hex,
                fingerprint=sha256(b'stranger').hexdigest())
    from datetime import datetime, timezone
    with pg.begin() as db:
        db.add(AssessmentExecution(id=execution_id, **args, status='PROCESSING', result_json=None,
                                   attempt_count=1, created_at=datetime.now(timezone.utc),
                                   updated_at=datetime.now(timezone.utc)))
    with pg.begin() as db:
        reconcile_as_failed(db, execution_id=execution_id, operator_id=uuid4(), authorized=True,
                            reason_code='WORKER_TERMINATED', ticket_reference='TEST-'+uuid4().hex)
    with pg() as db:
        assert db.get(AssessmentExecution, execution_id).status == 'FAILED'
        assert db.execute(select(AssessmentReconciliationEvent).where(
            AssessmentReconciliationEvent.execution_id == execution_id)).scalar_one().new_status == 'FAILED'
