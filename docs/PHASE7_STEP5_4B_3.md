# Phase 7 — Step 5.4b.3: Dependency wiring (fail closed)

## Status

Opt-in, NOT enabled in production. Adds composition of the Step 5.4b.2 endpoint,
Step 5.4a SQLAlchemy resolver, and Step 5.4 assessment service. Does not alter
`app/main.py` or `app/api/router.py` and does not create migrations.

## Important security finding

At inspection, public `app/api/conversation_turns.py` uses `user_id` in the URL
and accesses `get_db`, but its route signature contains no trusted authentication
dependency. A URL parameter is not an authenticated identity. It is NOT safe to
wire the new assessment endpoint by treating that URL value as trusted.

`install_assessment_endpoint` therefore refuses enablement without an explicit,
authoritative authenticated user dependency. This dependency must authenticate
requests and return the principal's UUID; it must not merely parse a header, path,
or request body value. Do not enable the endpoint before this dependency exists
and is verified with cross-user negative tests.

## Example composition (only AFTER trusted auth exists)

```python
# In your application factory, with a real authentication dependency:
from app.api.conversation_assessment_wiring import install_assessment_endpoint
install_assessment_endpoint(
    application, enabled=True,
    authenticated_identity_dependency=get_current_authenticated_user_id,
    context_from_session=trusted_communication_context_mapper,
    model_call=configured_structured_communication_model_call,
)
```

Do not copy placeholders as callable implementations. `model_call` must use a
structured, bounded provider with explicit consent/cost policy.

## Limitations to address before production

1. Authenticate all relevant conversation routes; ensure user path IDs are not considered authentication.
2. Confirm context mapping to `professional` or `conversational` from trusted persisted data.
3. Connect the existing LLM provider with response constraints, timeouts, and limits.
4. Establish durable idempotency keyed by user/session/turn and evidence hash;
   instance-local idempotency is not sufficient across requests or workers.
5. Add PostgreSQL/TestClient integration tests with two distinct principals and
   real authenticated session lifecycles. Current tests are configuration/HTTP
   guard tests, not production end-to-end authentication proofs.
6. Do not infer audio pronunciation from committed text. `VOICE_TEXT_UNKNOWN`
   remains a textual-only provenance indicator.

## Local validation

From `backend/`:

```powershell
python -m pytest -q tests/test_conversation_assessment_wiring.py
python -m pytest -q
alembic current
```

No frontend changes, no API calls in tests, no migrations.
