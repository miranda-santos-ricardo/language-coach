# Phase 7 Step 5.4a — Actual SQLAlchemy query integration

Based on the supplied `practice_session.py`, `conversation_turn.py`, `conversation_service.py`, `session.py` and the repository's public `language_profile.py` and `language_variant.py` sources.

## Read-only authorized boundary
- A **single joined SQL query** resolves turn, session, language profile and locale with `LanguageProfile.user_id == authenticated_user_id` within SQL.
- No assumed `ConversationTurn.user_id` column. Ownership is through `PracticeSession.language_profile_id`.
- `learner_text` is the persisted learner text; `coach_response` is never used.
- No migrations, endpoints or writes. No change to the existing ConversationService.
- Call `make_sqlalchemy_turn_resolver` with a **request-scoped** database Session; obtain `authenticated_user_id` from server-side authentication.

## Integration contracts requiring an application decision
- `context_from_session` is deliberately explicit: the session has `training_mode` and `communication_register`, not a literal `professional/conversational` field. Return one of these values after mapping actual app semantics. Never infer this from a client-provided context.
- `ConversationTurn` stores only `input_modality` and `learner_text`. For voice turns, the database does not record whether a transcript was edited. Therefore voice **fails closed** unless `voice_origin_from_turn` reads verifiable, persisted provenance. Do not pass a request-controlled callback in production.
- This resolver reads committed rows; it does not provide durable evaluation idempotency. `ConversationTurnAssessmentService` remains per-process. Distributed idempotency requires a separate persisted state machine and unique keys.
- Session status is not used to infer whether existing committed turns are valid; completed sessions can contain assessable historical turns. Enforce your app's explicit policies externally.
- Do not keep a transaction open across LLM network calls. Read evidence, close/commit the read transaction and assess separately, with an appropriate revision/immutability strategy.

## Validation
From `backend`:
```
python -m pytest -q tests/test_sqlalchemy_turn_resolver.py
python -m pytest -q
alembic current
```
Expected baseline: 683 existing + 10 new = **693** backend tests, `c5202601 (head)` if nothing else changed.

SQLite tests verify actual SQL joins and ownership predicates, not the PostgreSQL execution plan or production authentication middleware. No assessment is persisted by this increment.
