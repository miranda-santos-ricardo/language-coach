# Phase 7 — Step 5.4b.9: Authenticated Administrative Recovery

## Scope
Adds an **opt-in** privileged FastAPI endpoint wrapping the Step 5.4b.8 reconciliation primitive.
No application router is modified or automatically mounted. No migrations are added.

`POST /admin/assessments/{execution_id}/reconcile-as-failed`
Body: `{"reason_code":"WORKER_TERMINATED","ticket_reference":"INC-123"}`

The **admin-only** required scope is `conversation:assessment:reconcile`, distinct from `conversation:assess`.
The operator UUID is obtained only from the host-injected Bearer verifier, never from request body, URL, or custom headers.
The verifier must *actually* validate signatures, issuer, audience, expiry, revocation/account status. The test verifier is NOT production authentication.

State transition is `PROCESSING` → `FAILED` + reconciliation audit event in the same database transaction. `COMPLETED` and `FAILED` are not mutable using this route. A denied/missing/invalid request changes nothing. No LLM call or retry occurs.

### Installation
Import `install_assessment_admin_recovery` from `app.api.assessment_admin_recovery`, then call it with `enabled=True`, a real `verify_bearer_token`, and `session_dependency` returning a request-scoped SQLAlchemy Session. Default is disabled. The host should additionally require administrator MFA, network restrictions, incident-approval workflow, rate limiting, TLS, sensitive access logging, and operator revocation policies.

### Local checks
From `backend`:
```
python -m pytest -q tests/test_assessment_admin_recovery.py
python -m pytest -q
alembic current
```
Expected baseline: 779 existing passing tests + 10 new tests = 789 passing, with two PostgreSQL tests skipped until configured; migration remains `c5202603 (head)`.

### Safety limitations
Tests use SQLite and a stub token verifier. PostgreSQL concurrency tests from Step 5.4b.8 remain outstanding; do not activate operational endpoint until real verifier and Postgres validation are completed. The recovery endpoint **does not** clear idempotency claims or retry ambiguous LLM requests. The response does not contain the stored assessment content.
