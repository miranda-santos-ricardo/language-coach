# Phase 7 — Step 5.4b.6: Persistent Assessment Idempotency & Audit Evidence

Baseline supplied by user: 752 backend tests, `c5202601 (head)`.

## Delivered
- SQLAlchemy ORM ledger with unique key `(user_id, practice_session_id, turn_id, client_request_id, evaluator_version)`.
- Independent short DB transactions for atomic claim, result storage, replay, and failed state.
- A second service instance cannot call the provider when the same key is `PROCESSING` or `FAILED`; a `COMPLETED` record is replayed if the fingerprint agrees.
- Hash of committed evaluation inputs; no raw prompt, audio or tokens in ledger schema.
- 10 deterministic tests, including concurrency, isolation of keys, replay, validation and provider failures.
- Alembic migration `c5202602` branching directly from `c5202601` (verify this is the actual current project migration folder and no other child revision exists).

## Important limits
- This package provides a **repository/service building block**, not automatic activation in `main.py` and not HTTP route wiring. The existing Step 5.4b.3/4 composition remains disabled unless explicitly configured. It does not modify existing `ConversationTurnAssessmentService` or the production auth boundary. HTTP adoption must enforce SQL ownership first, including on a cached replay, then calculate fingerprint from **trusted committed text** and invoke the ledger. Never accept a client-provided fingerprint or identity.
- No exactly-once external execution guarantee: DB transaction and LLM operation are not atomic. No automatic retry of `PROCESSING` (including after server crash) or `FAILED`; an operator must reconcile provider status first, with a **new audit trail** for any explicit retry. Manual reconciliation, a PENDING queue, and failure recovery remain future work.
- The ledger stores JSON assessment results. They may contain quotations from learner text. Redact/minimize before storing and establish retention/encryption/access policy. No automatic PII filter is provided here.
- SQLite tests validate the unique constraint and concurrency contract for independent ledger instances; verify migration and parallel behavior on project PostgreSQL before enabling in production.
- The existing authenticated integration test suite uses a mocked verifier; live cryptographic verification is still outstanding.

## Installation
Extract zip at repo root. Check the application's Alembic versions path before copying the migration; it might be `backend/alembic/versions` or different. Verify `down_revision='c5202601'` matches your current graph.

Within `backend`:

```powershell
python -m pytest -q tests/test_persistent_assessment_idempotency.py
python -m pytest -q
alembic heads
alembic upgrade head
alembic current
```

Expected new targeted count: 10 passed. Expected full count if prior baseline remains unchanged: 762 passed. Expected Alembic head after upgrade: `c5202602 (head)`. **Back up your PostgreSQL database before migration.** Don't run `alembic upgrade head` if versions directory differs or another revision already branches from `c5202601`.

## Next step
Step 5.4b.7: authorized service composition + HTTP replay response semantics (`202` or `409` when busy), real Postgres integration and operator reconciliation policy, while preserving fail-closed auth.
