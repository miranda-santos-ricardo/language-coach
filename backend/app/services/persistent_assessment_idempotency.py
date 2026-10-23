"""Phase 7 Step 5.4b.6: SQL-backed claim, result replay and bounded audit.

Never holds a transaction across a provider call. PROCESSING is not automatically
reclaimed: a crash requires operator reconciliation to avoid ambiguous re-dispatch.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session


class AssessmentLedgerBase(DeclarativeBase):
    pass


class AssessmentExecution(AssessmentLedgerBase):
    __tablename__ = 'conversation_assessment_executions'
    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    practice_session_id: Mapped[UUID] = mapped_column(nullable=False)
    turn_id: Mapped[UUID] = mapped_column(nullable=False)
    client_request_id: Mapped[UUID] = mapped_column(nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(120), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint('user_id', 'practice_session_id', 'turn_id', 'client_request_id', 'evaluator_version', name='uq_assessment_execution_key'),
        CheckConstraint("status IN ('PROCESSING','COMPLETED','FAILED')", name='ck_assessment_execution_status'),
        Index('ix_assessment_execution_user_updated', 'user_id', 'updated_at'),
    )


class AssessmentBusy(Exception):
    """Duplicate dispatch is in progress or uncertain. Caller may return 409/202."""


class AssessmentConflict(Exception):
    """Turn fingerprint changed; do not reuse cached assessment."""


@dataclass(frozen=True)
class LedgerOutcome:
    status: str  # EXECUTED or REPLAYED
    execution_id: UUID
    result: dict[str, Any]


def evidence_fingerprint(*, text: str, locale: str, context: str, scenario: str,
                         origin: str, scenario_type: str, evaluator_version: str,
                         stt_original_available: bool) -> str:
    """Canonical hash of evaluation inputs; never log or persist submitted text."""
    value = [text, locale, context, scenario, origin, scenario_type, evaluator_version, stt_original_available]
    return sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


class PersistentAssessmentLedger:
    """Per-operation sessions must come from independent SQLAlchemy Session factory.

    Invoker MUST run the authorized turn resolver before ledger.execute, including
    on replay; this ledger does not authorize users. Only store *sanitized* model
    output: text quotation and user PII must be filtered by the caller if needed.
    """
    def __init__(self, session_factory: Callable[[], Session]):
        if not callable(session_factory):
            raise ValueError('Session factory required')
        self._factory = session_factory

    def execute(self, *, user_id: UUID, practice_session_id: UUID, turn_id: UUID,
                client_request_id: UUID, evaluator_version: str, fingerprint: str,
                evaluate: Callable[[], dict[str, Any]]) -> LedgerOutcome:
        key = (user_id, practice_session_id, turn_id, client_request_id, evaluator_version)
        if any(type(i) is not UUID for i in key[:4]) or not evaluator_version or len(evaluator_version) > 120:
            raise ValueError('Invalid assessment identifiers')
        if type(fingerprint) is not str or len(fingerprint) != 64 or any(c not in '0123456789abcdef' for c in fingerprint):
            raise ValueError('Invalid evidence fingerprint')
        if not callable(evaluate):
            raise ValueError('Evaluator required')
        now = datetime.now(timezone.utc)
        execution_id = uuid4()
        with self._factory() as db:
            db.add(AssessmentExecution(
                id=execution_id, user_id=user_id, practice_session_id=practice_session_id,
                turn_id=turn_id, client_request_id=client_request_id, evaluator_version=evaluator_version,
                fingerprint=fingerprint, status='PROCESSING', result_json=None,
                attempt_count=1, created_at=now, updated_at=now,
            ))
            try:
                db.commit()  # atomic uniqueness claim; no external call in transaction
                claimed = True
            except IntegrityError:
                db.rollback()
                claimed = False
            if not claimed:
                row = db.execute(select(AssessmentExecution).where(
                    AssessmentExecution.user_id == user_id,
                    AssessmentExecution.practice_session_id == practice_session_id,
                    AssessmentExecution.turn_id == turn_id,
                    AssessmentExecution.client_request_id == client_request_id,
                    AssessmentExecution.evaluator_version == evaluator_version,
                )).scalar_one()
                if row.fingerprint != fingerprint:
                    raise AssessmentConflict('Committed evidence changed')
                if row.status == 'COMPLETED' and isinstance(row.result_json, dict):
                    return LedgerOutcome('REPLAYED', row.id, row.result_json)
                raise AssessmentBusy('Existing execution is in progress or requires reconciliation')
        # Outside transaction: at most one request proceeds for each unique key.
        try:
            result = evaluate()
            if not isinstance(result, dict):
                raise TypeError('Assessment result must be a JSON object')
            # Force JSON serialization prior to committing a permanent result.
            result = json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False))
        except BaseException:
            self._mark_failed(execution_id)
            raise
        with self._factory() as db:
            row = db.get(AssessmentExecution, execution_id)
            if row is None or row.status != 'PROCESSING':
                raise AssessmentBusy('Execution state changed during evaluation')
            row.result_json = result
            row.status = 'COMPLETED'
            row.updated_at = datetime.now(timezone.utc)
            db.commit()
        return LedgerOutcome('EXECUTED', execution_id, result)

    def _mark_failed(self, execution_id: UUID) -> None:
        try:
            with self._factory() as db:
                row = db.get(AssessmentExecution, execution_id)
                if row is not None and row.status == 'PROCESSING':
                    row.status = 'FAILED'
                    row.updated_at = datetime.now(timezone.utc)
                    db.commit()
        except Exception:
            # A database outage leaves PROCESSING for operator reconciliation;
            # never silently retry ambiguous external provider execution.
            pass
