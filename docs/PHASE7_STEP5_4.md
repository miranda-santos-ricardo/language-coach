# Phase 7 — Step 5.4: Conversation Turn Assessment Integration

## Scope

**Incremental internal service, not a production FastAPI endpoint.** Provides a trusted projection (`CommittedTurnSnapshot`) and orchestration (`ConversationTurnAssessmentService`) for evaluation of an already committed learner turn. Reuses Step 5.1 evidence, Step 5.2 rubric and Step 5.3 controlled model adapter. No audio, schema migration, network, database or frontend changes.

## Trust boundaries

1. The endpoint or service caller obtains `authenticated_user_id` from authenticated session/security middleware — never from body/form fields.
2. A repository-backed `resolve_turn(authenticated_user_id, practice_session_id, conversation_turn_id)` **must verify** user/tenant/session ownership, that the turn is learner-authored, is committed, is not revoked and is eligible in its session lifecycle. It must return a `CommittedTurnSnapshot` built from trusted persisted records, with the **exact committed text** and the original `client_request_id`.
3. The orchestrator repeats snapshot identity checks and rejects mismatched IDs, uncommitted/assistant turns or invalid evidence. The `authorized_turn=True` flag is populated **only after** the trusted resolver returns; the flag is not a substitute for repository authorization.
4. The model receives submitted text as untrusted data through Step 5.3; only the existing rubric schema may be returned. No numeric grades or acoustic claims.
5. An identical repeat call returns the previously validated result without calling the model again **within the same service instance**. Changed text, source, scenario, locale, origin, rubric mode or evaluator version cause a conflict.

## Example service wiring (illustrative, not plug-and-play)

```python
from app.services.conversation_turn_assessment import ConversationTurnAssessmentService

service = ConversationTurnAssessmentService(
    resolve_turn=repository.resolve_committed_learner_turn,  # must enforce auth + ownership
    model_call=llm_adapter.evaluate_with_structured_json,
)
result = service.assess(
    authenticated_user_id=authenticated_principal.user_id,
    practice_session_id=stored_session_id,
    conversation_turn_id=stored_turn_id,
    client_request_id=stored_request_id,
    scenario_type='executive_update', evaluator_version='evaluator-v1',
)
```

## Security and design limitations

- **In-memory idempotency is not durable or distributed**. A process restart or multiple FastAPI workers can repeat model execution. Production must use an evaluation table with `(user_id, turn_id, idempotency_key)` uniqueness, status `PENDING/SUCCEEDED/FAILED`, lease/timeout/retry and a fingerprint of the canonical committed turn plus evaluator/rubric versions. Do not hold an SQL transaction over LLM network IO.
- The current service uses an `RLock` around the provider call for correctness in a single instance; this serializes requests and is **not production throughput architecture**.
- Caller must enforce consent/LLM provider policy, rate limits, budget, authorization, cancellation, deletion and retention. This service is not an access control implementation; it only consumes a trusted resolver. A provider may send submitted text to an external API if configured: require explicit product consent/settings.
- Hashing text supports equality detection, not proof of ownership, non-repudiation or tamper evidence. Store hashes only where justified; avoid logging transcripts.
- `ConversationTurn` ORM, route integration, actual database transaction boundaries, frontend and output persistence have not been modified because their live implementations were not available to inspect.
- Checks reject accidental mismatches, but a malicious or faulty resolver can attest false ownership. The integration needs security tests against the real DB and tenant filtering.

## Validation

From `backend`:

```powershell
python -m pytest -q tests/test_conversation_turn_assessment.py
python -m pytest -q
alembic current
```

New tests: **28 passed** in the isolated preparation workspace. Steps 5.1–5.4 combined: **109 passed**. Full regression projected from user-confirmed 637: **665** tests, subject to local validation. Alembic expected `c5202601 (head)`; no new migration.

## Acceptance / next increment

Step 5.4a (actual application wiring): inspect `ConversationTurn`, session repository, existing LLM service and routes; implement DB-authorized resolver, durable idempotency, tests for cross-user/cross-session, consent/budget and rollback/retry; only then add an HTTP/API and frontend indicator.
