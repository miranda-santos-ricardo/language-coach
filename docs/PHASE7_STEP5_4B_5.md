# Phase 7 — Step 5.4b.5: Authenticated Assessment Integration Testing

## Purpose
Add an isolated HTTP integration suite exercising the previously implemented authentication boundary, FastAPI wiring, SQLAlchemy authorized resolver, conversation evidence gate, and controlled evaluator. No production code or migrations changed.

## Files
- `backend/tests/test_authenticated_assessment_integration.py` (14 tests)

## Coverage
- Trusted identity resolved from a verifier-injected Bearer token (simulated verifier)
- SQLAlchemy owner predicates using two users and distinct profiles, sessions and turns
- Unknown voice transcript edit history evaluates only submitted committed text
- No ownership bypass by supplying a known session/turn/request UUID or spoofed headers
- Unknown and wrong session/turn IDs return generic errors without invoking evaluator
- Forged client text, identity or modality rejected by HTTP payload validation
- Missing/invalid tokens and missing scope denied
- Insufficient evidence abstention and malformed evaluator result fail-closed
- Disabled feature does not expose endpoint
- Repeated requests presently call the evaluator twice: **idempotency is not durable**

## Test scope and limits
The integration tests exercise production *control-flow implementations* but run against isolated SQLite tables with the same relevant join topology as production. The test monkeypatches `app.models` to supply those model doubles. The Bearer verifier is an injected deterministic test double, **not** a cryptographic JWT/OIDC verifier. The evaluator is a deterministic mock, with no provider/network calls. Tests are NOT an end-to-end staging or live PostgreSQL security certification. The endpoint remains off by default.

## Run
From `backend` after extracting into the repository root:

```powershell
python -m pytest -q tests/test_authenticated_assessment_integration.py
python -m pytest -q
alembic current
```

Expected new suite: `14 passed`; expected overall total based on prior user's `738 passed`: `752 passed` (subject to existing suite/installed versions). Alembic expected `c5202601 (head)`.

## Next steps before activation
1. Add a real token issuer/provider integration or trusted session-based auth; validate signature, audience, issuer, expiry, revocation, user status.
2. Repeat isolation tests against real PostgreSQL and actual ORM models using full app factory and test DB.
3. Implement durable idempotency/unique transaction key before live LLM use; each HTTP request currently recreates the assessment service and its in-memory cache.
4. Bound LLM cost and concurrency, and log safe audit metadata without raw PII.
5. Bind authoritative context mapping to persisted practice session metadata.
