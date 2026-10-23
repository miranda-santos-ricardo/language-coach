"""Opt-in administrative reconciliation HTTP boundary, Step 5.4b.9.

The host MUST inject a cryptographic token verifier; no URL identity fallback.
This route does not call an LLM and cannot release an idempotency reservation.
"""
from __future__ import annotations

from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.conversation_assessment_auth import VerifiedIdentity
from app.services.assessment_reconciliation import ReconciliationDenied, reconcile_as_failed

_ADMIN_SCOPE = "conversation:assessment:reconcile"
_bearer = HTTPBearer(auto_error=False)


class AdminRecoverySetupError(ValueError):
    pass


class ReconcileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    reason_code: str = Field(min_length=1, max_length=60)
    ticket_reference: str = Field(min_length=1, max_length=120)


def install_assessment_admin_recovery(
    app: FastAPI, *, enabled: bool = False,
    verify_bearer_token: Callable[[str], VerifiedIdentity] | None = None,
    session_dependency: Callable | None = None,
) -> bool:
    """Explicitly mount a privileged-only route, with fail-closed preflight.

    `verify_bearer_token` MUST validate token signature, issuer, audience,
    expiry, and revocation/account status as relevant. This installer does not.
    """
    if not isinstance(app, FastAPI) or type(enabled) is not bool:
        raise AdminRecoverySetupError("Explicit FastAPI enablement required")
    if not enabled:
        return False
    if not callable(verify_bearer_token) or not callable(session_dependency):
        raise AdminRecoverySetupError("Verified token and database session required")
    if getattr(app.state, "_assessment_admin_recovery_installed", False):
        raise AdminRecoverySetupError("Recovery endpoint already installed")

    def authorized_operator(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> UUID:
        if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
            raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
        try:
            identity = verify_bearer_token(credentials.credentials)
        except Exception:
            raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"}) from None
        if (type(identity) is not VerifiedIdentity or type(identity.user_id) is not UUID
                or type(identity.active) is not bool or not identity.active
                or type(identity.scopes) is not frozenset or not all(type(s) is str for s in identity.scopes)
                or _ADMIN_SCOPE not in identity.scopes):
            raise HTTPException(403, "Recovery not permitted")
        return identity.user_id

    router = APIRouter(prefix="/admin/assessments", tags=["assessment-admin"])

    @router.post("/{execution_id}/reconcile-as-failed")
    def reconcile(
        execution_id: UUID,
        payload: ReconcileRequest,
        operator_id: UUID = Depends(authorized_operator),
        db: Session = Depends(session_dependency),
    ) -> dict:
        if not isinstance(db, Session):
            raise HTTPException(503, "Recovery unavailable")
        try:
            with db.begin():
                outcome = reconcile_as_failed(
                    db, execution_id=execution_id, operator_id=operator_id, authorized=True,
                    reason_code=payload.reason_code, ticket_reference=payload.ticket_reference,
                )
        except ReconciliationDenied:
            db.rollback()
            raise HTTPException(409, "Reconciliation unavailable") from None
        except Exception:
            db.rollback()
            raise HTTPException(503, "Recovery unavailable") from None
        return {"event_id": str(outcome.event_id), "execution_id": str(outcome.execution_id), "status": outcome.status}

    app.include_router(router)
    app.state._assessment_admin_recovery_installed = True
    return True
