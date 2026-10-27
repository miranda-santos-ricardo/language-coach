# Phase 8 — Step 8.4.1h.3 — Authenticated text conversation

## Scope
- Existing guarded `conversation_turns` router is reused in opt-in pilot app.
- Frontend reads pages of turns and sends text-only messages with a fresh `client_request_id`.
- Controlled pilot continues to require OIDC. Legacy local mode is unchanged.
- No migrations, no experimental pronunciation/fluency assessment, no new API integrations.

## Safety and limitations
- Backend owner authorization is applied to each user-scoped route by `learner_pilot_routes.py`.
- UI never automatically retries a failed POST: a timeout or 5xx can mean the LLM call or transaction completed. Inspect history and reconcile manually before resubmission.
- UI shows only `overall_assessment` for persisted history; detailed feedback layout is deferred.
- History fetch is 50 turns (first page only); pagination UX is deferred.
- Text POST can invoke the **existing paid LLM conversation provider** if the host opts into and configures the pilot. No fake provider is installed. Leave pilot disabled until costs and authorization are validated.
- `crypto.randomUUID()` needs a secure context. Development over localhost/HTTPS is expected.
- Pilot is **not** declared ready for real users; external IdP, key handling, nonce validation, cost limits, concurrency and end-to-end UX need further review.

## Verification (PowerShell)
```powershell
cd frontend
npm test -- --run src/test/pilotConversation.test.ts
npm test -- --run
npm run build
cd ../backend
python -m pytest -q tests/test_learner_external_oidc_runtime.py tests/test_conversation_submit_api.py tests/test_conversation_retrieval_api.py
python -m pytest -q
```

## Acceptance
- Bearer sent only to configured trusted origin, never as cookie.
- GET/POST stays within owner/profile/session URL and rejects malformed identifiers.
- POST sends text, `input_modality=text`, and UUID idempotency key.
- Expired tokens / 401 cause denial, and 404 doesn't reveal cross-user resources.
- Unknown POST outcome cannot be retried automatically.
- Existing mode and tests remain unaffected.
