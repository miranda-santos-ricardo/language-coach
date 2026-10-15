# Phase 5 / Step 2 / Increment 2

Apply over an installation where Increment 1 is already applied. Only `backend/tests/test_conversation_persistence.py` changes. No new migrations, endpoint changes, or schema changes.

## Tests added
- Rollback of a successfully flushed turn and feedback
- Failed subsequent transaction preserves previously committed turn
- Request ID scoped to practice session
- DB CHECK constraints for index, modality and space-only inputs
- DB foreign keys reject orphan records
- Pagination limits and offsets

## Commands
```bash
cd backend
python -m pytest -q tests/test_conversation_persistence.py
python -m pytest -q tests/test_migrations.py tests/test_models.py
python -m pytest -q
alembic heads
alembic current
```

Expected: 14 tests in `test_conversation_persistence.py`, all passing. `alembic heads` should show `c5202601`; `alembic current` should show `c5202601` if previously upgraded. No migration is required for this increment.

## PostgreSQL-only optional verification
Use a disposable local development/test PostgreSQL database; never test downgrade on your real populated database.

```bash
# Point DATABASE_URL at a disposable PostgreSQL database using your project's config.
alembic upgrade head
alembic current
alembic downgrade ba35d4c616d6
alembic upgrade head
```

## Known limits
- These repository tests run against SQLite with FK enforcement, not PostgreSQL.
- A SQL `trim()` check rejects space-only text but may accept other whitespace-only text such as tabs; Pydantic/service input validation must reject `not text.strip()` in Steps 5-7. A later DB constraint change would require a new migration, not rewriting applied `c5202601`.
- Database uniqueness does not ensure exactly-once LLM execution under concurrent requests. Step 6 must enforce single-flight per session and the idempotency contract.
- Full suite could not be collected in the packaging environment because `psycopg` and `openai` were not installed. Run the full suite in your configured project environment.
