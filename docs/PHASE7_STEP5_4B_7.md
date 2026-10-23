# Phase 7 — Step 5.4b.7 — Persistent Ledger Integration & Recovery Policy

## Scope

Provides a separate **opt-in** HTTP mount, `install_persistent_assessment_endpoint`, integrating Steps 5.4, 5.4a, 5.4b.4, and 5.4b.6. It does **not** alter existing app router or activate provider calls on its own.

## Contract

`POST /practice-sessions/{practice_session_id}/turns/{turn_id}/assessment` with `{ "client_request_id": "<uuid>" }`, and real `Authorization: Bearer` credentials verified by the **host-provided** verifier.

- 200 (`execution_status=EXECUTED`) on newly completed assessment.
- 200 (`execution_status=REPLAYED`) on previously completed assessment after a **fresh ownership + turn-fingerprint** check.
- 401 for missing/invalid bearer; 403 for disabled account/missing scope (host-supplied identity verification).
- 404 for unavailable, foreign-owned or mismatched committed turn.
- 409 `Assessment evidence changed` when a previously used unique key's evidence no longer matches.
- 409 `Assessment execution unavailable; reconciliation required` when the key is already PROCESSING or FAILED. No provider retry.
- 503 on evaluator/database failure. Provider details are not exposed.
- 422 for UUID/body schema validation failures.

The response contains the assessment result, stable execution UUID, and execution status; **no raw transcript** is returned. Warning: `assessment` may contain supporting quotes; apply privacy/retention policy before using with real PII.

## Implementation guarantees and boundaries

1. Every request reauthenticates the Bearer and uses SQLAlchemy owner filtering **before** ledger read/write, including replay.
2. Evidence fingerprint covers committed text, locale, scenario, context, origin, STT flag, scenario type and evaluator version.
3. SQL unique constraint permits a single winning claim per key. The ledger commits the claim before provider execution; no ledger transaction spans the provider call.
4. COMPLETED replays stored result from a new request and a new service instance.
5. PROCESSING and FAILED are deliberately not restarted automatically, even after a crash: it is impossible to infer reliably whether an outbound LLM request ran. Operator reconciliation is required. The operation does not currently support resetting this state through an HTTP API.
6. `VOICE_TEXT_UNKNOWN` can be assessed *as confirmed text only*.
7. This installer and legacy `install_authenticated_assessment_endpoint` register the **same route**. Mount only one; both mark `_conversation_assessment_installed`.

**Not yet guaranteed**: provider-level exactly once (an external LLM can process a request before a failure), recovery SLA, PostgreSQL simultaneous-worker locking validation, signed token verification (must be supplied), distributed rate limiting, cost controls, quote redaction, data retention/cleanup, provider timeout/circuit breaker, or application registration. Distinguish durable at-most-one automatic dispatch from true exactly-once execution.

## Required host dependencies

```python
from app.api.conversation_assessment_persistent import install_persistent_assessment_endpoint

install_persistent_assessment_endpoint(
    app,
    enabled=True,  # only behind a feature gate once all prerequisites are ready
    verify_bearer_token=real_verified_token_provider,
    context_from_session=trusted_context_mapping,
    model_call=controlled_evaluator_provider,
    session_dependency=get_db,
    ledger_session_factory=SessionLocal,
)
```

`ledger_session_factory` must yield independent SQLAlchemy sessions, not reuse `get_db`'s request-scoped session. Schema migration `c5202602` must already be applied. Do **not** use the test verifier in a deployed environment. This snippet is an explicit integration example, not a recommendation to enable yet.

## Validation (run from `backend`)

```powershell
python -m pytest -q tests/test_persistent_assessment_endpoint.py
python -m pytest -q
alembic current
```

Expected: **9 new tests** (771 total if the existing 762 all pass), `c5202602 (head)`; no migration added in this step. Run tests in the *actual repo*: isolated reconstructed-code tests do not replace full regression.

## Follow-up prerequisites before activation

- PostgreSQL concurrency tests with independent processes / separate DB connections.
- Cryptographically validated Bearer using actual app users and production auth.
- An explicit operator-only, audited reconciliation process for old PROCESSING / FAILED rows, including when provider execution might have occurred.
- Model-output data minimization, PII/retention and budget enforcement.
- Real application wiring and end-to-end tests; frontend integration after security gates.
