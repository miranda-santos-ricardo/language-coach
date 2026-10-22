# Phase 7 — Step 3.4: Offline integration seam

## Scope

An additive, dependency-injected orchestration boundary binds an *authorized* voice turn to an audio recording attempt and the Step 3.1 evidence-gated provider. It produces a validated `SpeechAssessment` with `INSUFFICIENT_EVIDENCE`, a `NOT_ASSESSED` pronunciation dimension and **no score**. No endpoint, DB migration, model inference or audio storage is added.

The previous step's audio laboratory and human calibration harness are **not pronunciation engines**; no pronunciation outcome can be calibrated yet.

## Trust contract

The `resolve_authorized_turn(requester_user_id, conversation_turn_id)` callback MUST be implemented using trusted application repositories/services. It must verify user ownership of the turn, session and profile; recording attempt/turn association; expected language/profile; session lifecycle; and the caller's identity. The seam verifies returned user/turn IDs, voice modality and active status, but it **cannot itself guarantee** the callback's correctness or that the supplied recording is authentic/associated. Never construct the callback from untrusted request fields.

No MIME content sniffing, FFmpeg processing, audio duration verification, replay prevention across processes, or transactional association is attempted here. MIME is only an allow-list check. Do not expose this seam as an API before the missing validations are implemented.

## Idempotency and concurrency

Duplicate `(requester, turn, client_request_id)` calls with identical recording ID, MIME and SHA-256 return the same assessment, within a single integrator instance. Changed payloads produce a conflict. Every request re-authorizes, including replay. A process-local lock serializes operations in this instance. This is **not** sufficient for multiple workers, service restart, durable storage or transaction-level conflicts: those require a DB-backed unique constraint and transaction/locking strategy after inspection of the current DB schema.

Only output metadata and hash are cached (not raw audio); however the cache also contains learner transcript and submitted text within `SpeechAssessment`. It must be scoped to ephemeral development, and instance lifetime should be short. Production requires a cache lifecycle and deletion policy.

## Security and quality limitations

- Consent is a caller-supplied flag here, **not a verified consent record**. Production must check a consent event or similarly authoritative signal.
- No original recording audio is saved. The hash is derived from bytes and must not be logged; neither should transcripts.
- Audio is not decoded, so malformed bytes with an allowed MIME type may pass. The test deliberately uses non-audio bytes to assert contract behavior only.
- Audio comparison and timing analysis are not integrated; no acoustic evidence is reported.
- `NOT_ASSESSED` means pronunciation accuracy was not established, not that the learner failed.
- Provider calls happen under the per-instance lock. Production should separately coordinate without holding DB locks during long model inference.
- No human corpus, fairness or phoneme scoring validation has been completed.

## Validation

From `backend/`:

```bash
python -m pytest -q tests/test_pronunciation_mvp_integration.py
python -m pytest -q
alembic current
```

No frontend changes. The expected backend total, assuming the latest baseline (376) is unchanged, is 398 tests.

## Acceptance status

This incremental seam may be accepted after the new tests and full regression pass. **Step 3.4 production integration and Phase 7 pronunciation MVP are NOT complete.** Next: inspect actual `ConversationTurn` / `PracticeSession` repos, consent plumbing, recording lifecycle and current idempotency implementation before endpoint + transactional persistence implementation. Do not expose this prototype to users as measured pronunciation feedback.
