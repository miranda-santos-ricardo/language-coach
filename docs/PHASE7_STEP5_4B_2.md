# Phase 7 — Step 5.4b.2: Optional FastAPI Assessment Endpoint

## Delivery scope

- New router factory in `backend/app/api/conversation_assessment.py`.
- No changes to existing routes, DB models, migrations or frontend.
- No automatic route registration, background work or LLM calls.
- Tests use mock authenticated identity and assessment service (zero API cost).
- HTTP path: `POST /practice-sessions/{practice_session_id}/turns/{turn_id}/assessment`.
- Payload: `{"client_request_id":"<UUID of committed learner turn>"}`. Text, user_id and modality are forbidden in the body.
- Success: assessment draft and metadata without learner text/audio/raw model response.

## Application wiring: REQUIRED before real use

The host application must supply two FastAPI dependencies:

1. `get_authenticated_user_id`: return the authenticated UUID derived from the **existing** auth stack, never from request fields. Return a 401 if unauthenticated.
2. `get_assessment_service`: return a `ConversationTurnAssessmentService` that uses the authorized `make_sqlalchemy_turn_resolver` bound to a *request-scoped* SQLAlchemy Session, the session-context mapper, and a configured LLM adapter. See Steps 5.3, 5.4 and 5.4a. This endpoint does not automatically wire those existing dependencies.

Mount only after those dependencies have been audited:

```python
app.include_router(create_conversation_assessment_router(
    get_authenticated_user_id=YOUR_EXISTING_AUTH_DEPENDENCY,
    get_assessment_service=YOUR_INJECTED_ASSESSMENT_SERVICE,
    scenario_type='general',
    evaluator_version='communication-rubric-v1',
))
```

**Important:** `get_assessment_service` creates an object per request only if the host dependency does so. An ephemeral per-request service **does not** provide idempotency across HTTP requests. Even a long-lived service cannot safely hold a request-scoped DB Session between requests. Proper cross-worker idempotency requires durable claim/result storage, unique keys and a transaction protocol. This package does not claim that guarantee.

## Response/status policy

- `200` success; response includes `text_sha256` (not original text) and structured assessment.
- `401` unexpected/missing authenticated UUID if dependency returns invalid identity.
- `404` controlled evaluation or authorization failure, avoiding existence disclosure. **Some evaluator failures are also mapped to 404**; this is deliberately conservative but should be refined before public deployment.
- `503` unexpected failure or unavailable integration.
- `422` invalid UUID or extra fields in request.

The HTTP layer is **opt-in and experimental**, not a production-ready security boundary. Do not enable before validating auth, repository isolation and model-adapter policy against your actual application.

## Tests

```powershell
cd backend
python -m pytest -q tests/test_conversation_assessment_endpoint.py
python -m pytest -q
alembic current
```

8 new tests passed isolated in the preparation environment; baseline previously reported 706 backend tests, hence 714 expected if no existing tests changed. Full backend regression must be run locally.

## Follow-up gates

- Inspect auth/routing (`app/main.py`, existing auth dependency) before mounting.
- Verify PostgreSQL authorization under actual dependency injection.
- Add durable idempotency and request-state coordination before multi-worker use.
- Make assessment explicitly opt-in, off on default, preserve existing conversation path.
- Use a model adapter honoring structured output, timeout and budget caps.
- Integrate observability without logging learner text.
- Evaluate timeout behavior and server-side cancellation.
