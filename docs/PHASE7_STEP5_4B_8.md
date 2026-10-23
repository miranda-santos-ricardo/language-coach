# Phase 7 — Step 5.4b.8 — PostgreSQL Concurrency & Recovery Validation

## Baseline
- Before change: 771 backend tests, Alembic `c5202602 (head)`.
- Increment: 8 deterministic reconciliation tests and 2 optional PostgreSQL integration tests.
- Expected without PostgreSQL URL: **779 passed, 2 skipped** (assuming existing 771 stay green).
- Expected with a working isolated PostgreSQL database: **781 passed**.
- New revision: `c5202603`.

## What is delivered
1. `assessment_reconciliation.py`: a **non-HTTP** privileged reconciliation operation, with a `SELECT ... FOR UPDATE` lock on PostgreSQL and an audit event in the caller's transaction.
2. Alembic migration adding append-only-by-application `conversation_assessment_reconciliation_events`.
3. Eight deterministic tests using SQLite with a disposable file DB.
4. Two opt-in integration tests against disposable PostgreSQL using **independent SQLAlchemy sessions/connections**. One verifies competing claims across two ledger instances, replay, and a single evaluator invocation; one verifies reconciliation persistence.

## Safety and precise guarantees
- The caller must authenticate and authorize the operator **outside this function**, passing a verified `authorized=True` flag. This is a service API, not an administrative endpoint or authentication system. Do not expose it to clients.
- Only `PROCESSING -> FAILED` is allowed. `COMPLETED` and `FAILED` cannot be overwritten. A previously ambiguous provider call is **never automatically retried**; the unique-key record remains occupied.
- `ticket_reference` must refer to an approved incident/change ticket. Use categorical `reason_code` (e.g. `WORKER_TERMINATED`, `UNKNOWN_PROVIDER_OUTCOME`) and never place learner content or credentials in these fields.
- PostgreSQL `FOR UPDATE` serializes concurrent reconciliation attempts. The transactional audit event is inserted in the same commit. For production, enforce database permissions preventing updates/deletes to audit rows and set a retention policy.
- The current ledger protects **per unique request + evaluator version**, not against clients generating different request IDs for the same turn. The existing service also does not provide distributed exactly-once behavior at the external LLM; a crash after provider response but before DB commit remains ambiguous.
- PostgreSQL tests are opt-in; passing SQLite tests alone does **not** validate PostgreSQL locking or production security.
- The added PostgreSQL tests leave test-created rows in the disposable database for diagnostics. Use a dedicated disposable database only. Never point `ASSESSMENT_TEST_POSTGRES_URL` at production or development databases with real learner data.

## Install / verify
Unpack the ZIP into the **repository root**, preserving relative paths. From `backend`:

```powershell
python -m pytest -q tests/test_assessment_reconciliation.py tests/test_postgres_assessment_concurrency.py
python -m pytest -q
alembic heads
```

Verify only `c5202603` is head, back up the database, then:

```powershell
alembic upgrade head
alembic current
```

To validate PostgreSQL with an **empty disposable test database** (and driver `psycopg` installed), migrate that database separately by setting the existing project's Alembic DB URL to that isolated DB, then:

```powershell
$env:ASSESSMENT_TEST_POSTGRES_URL = "postgresql+psycopg://USER:PASSWORD@localhost:5432/language_coach_test"
python -m pytest -q tests/test_postgres_assessment_concurrency.py
Remove-Item Env:ASSESSMENT_TEST_POSTGRES_URL
```

Check setup-specific connection strings and existing Alembic configuration; setting `ASSESSMENT_TEST_POSTGRES_URL` **does not** modify Alembic's target. PostgreSQL service, driver and schema must be available. Never place production credentials in committed files.

## Known gaps / next step
- No real cryptographic Bearer verifier, privileged admin authentication/UI, rate limiting, or app registration here.
- No automatic retry or ambiguous-result resolution with provider receipts; manual review is required.
- For thorough contention testing, add separate **processes** and a PostgreSQL transaction-failure injection test; these tests use separate SQLAlchemy sessions and engine connections but thread concurrency inside one process.
- The endpoint remains disabled by default. Recommend Step 5.4b.9: real authenticated operator integration, PostgreSQL end-to-end validation, operational controls.
