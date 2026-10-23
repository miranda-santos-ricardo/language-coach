# Phase 7 — Step 5.4a: Authorized Repository Boundary

## Scope
This is an **integration-ready boundary**, NOT a completed integration into real SQLAlchemy entities. Current repository sources could not be inspected. The new adapter projects results from two authenticated application-owned repository callbacks into the existing `CommittedTurnSnapshot` contract from Step 5.4.

## Critical requirements for real wiring

1. `fetch_session(auth_user_id, session_id)` MUST query by BOTH primary key and the authenticated owner, including relevant tenant/soft-delete/status rules; return `AuthorizedSessionRow` or None. Do not accept `user_id` from the request payload.
2. `fetch_turn(auth_user_id, session_id, turn_id)` MUST query by turn id, session foreign key, and authenticated owner; return `PersistedLearnerTurnRow` or None. Verify committed learner role and use exact persisted submitted text rather than mutable draft or assistant reply.
3. Perform both reads in a consistent DB transaction/snapshot. Do not hold a transaction open across LLM network calls. Recheck text digest / revision before writing results.
4. A UUID `client_request_id` must reflect the persisted turn's actual idempotency key. If current schema uses strings or nullable IDs, design migration explicitly; do not manufacture keys silently.
5. Return origins aligned to Step 5.1 (`TYPED`, `STT_UNEDITED`, `USER_EDITED`); identify how origin and original STT availability are persisted. If absent, **fail closed** and plan schema evolution.
6. Durable idempotency, distributed workers, result persistence, transaction concurrency and HTTP endpoint are NOT implemented here. No new migration has been added.

## Files needed to finish genuine ORM integration
Run the optional collector from the repository root; review the archive and send relevant files. At minimum: `backend/app/models/practice_session.py`, `backend/app/models/conversation_turn.py` (names may vary), conversation service, sessions/turn routes, auth dependencies, database session setup, and existing isolation/idempotency tests.

## Validation
```powershell
cd backend
python -m pytest -q tests/test_conversation_repository_adapter.py
python -m pytest -q
alembic current
```
Expected baseline: 665 + 18 = **683** if all prior tests are present. Tests use in-memory mocked repository callbacks, not a real database.
