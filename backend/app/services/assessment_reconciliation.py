"""Administrative, non-dispatching reconciliation of ambiguous assessments.

A separate privileged caller must authenticate/authorize the human operator before
calling reconcile(). This module offers no HTTP endpoint and never calls a model.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.services.persistent_assessment_idempotency import AssessmentExecution, AssessmentLedgerBase


class AssessmentReconciliationEvent(AssessmentLedgerBase):
    __tablename__ = 'conversation_assessment_reconciliation_events'

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    execution_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('conversation_assessment_executions.id'), nullable=False
    )
    operator_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(20), nullable=False)
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(60), nullable=False)
    ticket_reference: Mapped[str] = mapped_column(String(120), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReconciliationDenied(Exception):
    """Missing authorization, invalid decision or unsafe state transition."""


@dataclass(frozen=True)
class ReconciliationOutcome:
    event_id: UUID
    execution_id: UUID
    status: str


def reconcile_as_failed(
    db: Session, *, execution_id: UUID, operator_id: UUID, authorized: bool,
    reason_code: str, ticket_reference: str,
) -> ReconciliationOutcome:
    """Resolve stranded PROCESSING -> FAILED without external provider dispatch.

    Does not clear the unique key, grant retries, or synthesize results. A completed
    evaluation must never be changed by this operation. Must be invoked only from
    a privileged, audited administrative context. Row locking serializes decisions
    with other reconciliation requests on PostgreSQL.
    """
    if authorized is not True or type(execution_id) is not UUID or type(operator_id) is not UUID:
        raise ReconciliationDenied('Privileged verified operator required')
    if not isinstance(reason_code, str) or not reason_code.strip() or len(reason_code) > 60 or not reason_code.replace('_','').replace('-','').isalnum():
        raise ReconciliationDenied('Valid categorical reason code required')
    if not isinstance(ticket_reference, str) or not ticket_reference.strip() or len(ticket_reference) > 120:
        raise ReconciliationDenied('External ticket reference required')
    # Caller owns transaction; rollback on any error to avoid partially applying state.
    row = db.execute(select(AssessmentExecution).where(AssessmentExecution.id == execution_id).with_for_update()).scalar_one_or_none()
    if row is None or row.status != 'PROCESSING':
        raise ReconciliationDenied('Only PROCESSING records can be reconciled')
    now = datetime.now(timezone.utc)
    event_id = uuid4()
    row.status = 'FAILED'
    row.updated_at = now
    db.add(AssessmentReconciliationEvent(
        id=event_id, execution_id=execution_id, operator_id=operator_id,
        action='MARK_UNCERTAIN_AS_FAILED', previous_status='PROCESSING', new_status='FAILED',
        reason_code=reason_code, ticket_reference=ticket_reference, occurred_at=now,
    ))
    db.flush()
    return ReconciliationOutcome(event_id, execution_id, 'FAILED')
