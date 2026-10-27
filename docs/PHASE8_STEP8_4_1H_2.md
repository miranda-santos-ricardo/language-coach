# Phase 8 — Step 8.4.1h.2 — Authenticated Practice Session Lifecycle

## Scope
This increment extends the isolated opt-in OIDC pilot frontend only, reusing existing guarded backend endpoints. The existing local UI, `app.main`, database schema, experimental assessors, transcription, and conversation submission remain unchanged.

### Supported operations
- Choose one of the authenticated user's profiles (obtained from `/pilot/me` and guarded `/users/{id}/language-profiles`).
- List sessions by profile; create with existing `PracticeSessionCreate` contract (`training_mode`, `register`, optional `target_cefr`/`scenario_key`).
- Retrieve an existing session to resume the *session selection only*. Conversations and audio are not yet available.
- Complete or abandon an active session using the original session service.
- Use bearer authentication, no cookies/credentials, no redirects, no token persistence, HTTPS (localhost HTTP allowed for development).
- 401 causes local sign-out; other errors remain visible without exposing tokens.

## Trust boundaries
The client-supplied user/profile/session UUIDs are not authoritative. The OIDC verifier resolves the internal user from a persisted external identity link. The guarded pilot router checks that the path user ID matches the authenticated user; the pre-existing service validates that the profile/session belongs to that user. **Never expose legacy public `/users` routes in the pilot deployment.**

## Excluded / remaining blockers
- No voice, conversation messages, STT/TTS, LLM calls, refresh token handling, provider logout, nonce/ID token validation, provider-side revocation proof, administrative governance, or real OIDC provider integration.
- No retry of mutations after ambiguous network failures. A new create requires intentional interaction; existing session creates are not idempotent.
- Race conditions and real DB isolation still require end-to-end homologation. Logout only removes frontend tokens, not server/provider-issued tokens.
- Runtime pilot setup and configuration remain opt-in and must not be made publicly accessible until real OIDC and remaining security gates are proven.

## Validation (PowerShell)
```powershell
cd frontend
npm test -- --run src/test/pilotSessions.test.ts
npm test -- --run
npm run build
cd ../backend
python -m pytest -q tests/test_learner_external_oidc_runtime.py tests/test_practice_session_api.py
python -m pytest -q
```

## Acceptance
1. Unauthorized, expired and invalid-resource requests never execute session operations.
2. Create/list/get/complete/abandon use guarded endpoints and preserve ownership isolation.
3. Profile change clears selected session and refreshes data.
4. 401 clears local session; other failures display safe messages.
5. Existing local mode and experimental feature flags are unchanged.
6. All frontend/backend tests and frontend build pass in the user's environment.

**Status:** awaiting user validation; do not mark PILOT_READY.
