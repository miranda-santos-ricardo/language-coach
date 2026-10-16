# Phase 5 / Step 7 / Increment 1 — Submit Conversation Turn API

Incremental patch on top of validated Step 6.2. Extract from repository root.

## Files
- New backend/app/schemas/conversation.py
- New backend/app/services/conversation_api_dependencies.py
- New backend/app/api/conversation_turns.py
- Modified backend/app/api/router.py
- New backend/tests/test_conversation_submit_api.py

## Commands
```bash
cd backend
python -m pytest -q tests/test_conversation_submit_api.py
python -m pytest -q
alembic current
```

Expected: 17 directed tests and baseline 240 + 17 = 257 backend tests (subject to test environment and collection). Alembic revision c5202601 (head). No migration, frontend modifications, or API token usage in tests.

## Contract
POST /users/{user_id}/language-profiles/{profile_id}/sessions/{practice_session_id}/turns

JSON request: text (1–4000 chars), input_modality (`text`/`voice`), client_request_id (UUID).

201 response: turn_id, turn_index, coach_response, feedback (nested structured schema), replayed, prompt_version, model. Replay returns 201 and replayed=true. Consider using 200 for replay if API consumers need it, but current contract uses 201 consistently.

Error mapping: 400 invalid learner text after trim; 404 ownership chain; 409 inactive/busy/conflicting request; 422 invalid payload from Pydantic; 502 invalid provider output; 503 configuration/provider/db errors; 504 timeout. Unexpected exceptions are intentionally not intercepted. Authentication limitation remains. Do not expose this API publicly before real authentication.

## Known limitations
- Test suite could not be run in assistant container: `psycopg` missing; this is not a passing test claim.
- Integration uses a fake LLM; production provider requires `OPENAI_API_KEY` and correct runtime network configuration.
- Existing `ConversationService` controls transaction lifecycle and assumes a dedicated DB session.
- PostgreSQL advisory lock must still be tested with two independent DB connections.
- Reading history/detail endpoints are reserved for Step 7 Increment 2.
