# Phase 8 — Step 8.4.1h (increment 1): authenticated profile read

## Scope
- Adds `GET /pilot/me` to the **isolated** `create_external_oidc_learner_pilot_app` only.
- The backend obtains user ID from the verified access token and persistent OIDC link, never from request parameters.
- Adds standalone `createPilotApi`: Bearer authorization with `credentials: omit`, no redirects, no-cache, no token persistence.
- In the opt-in React pilot shell, fetches `/pilot/me`, then reads only the returned user's profiles.
- Existing public local-first app and the `UserSelector` are untouched. No writes, voice or LLM calls added.

## Security considerations
- This is a read-only incremental integration. A forged user ID cannot be entered in this flow, but the backend must still deny cross-user access.
- The client never treats its local claims as authentication; the backend verifies every call.
- On HTTP 401 the in-memory token is discarded; 403/404 show nonsensitive status messages.
- Login callback still needs ID-token nonce verification, StrictMode lifecycle review, and IdP end-to-end testing before pilot activation.
- No browser refresh-token rotation, IdP logout or backend revocation on logout exists yet.
- Token expiration is checked when a request is made. Idle-time expiration UX is deferred.
- `VITE_PILOT_API_BASE_URL` must be the trusted **HTTPS origin** of the isolated pilot API. No secrets in Vite env vars.
- Any deployment must NOT expose the legacy unguarded app alongside the isolated protected app.

## Windows validation
```powershell
cd backend
python -m pytest -q tests/test_learner_external_oidc_runtime.py
python -m pytest -q
cd ../frontend
npm test -- --run src/test/pilotApi.test.ts
npm test -- --run
npm run build
```

## Acceptance
- Protected `/pilot/me` returns only server-resolved account; denies missing/revoked tokens.
- Authenticated frontend requests use Bearer only for configured trusted API origin.
- Existing frontend behavior remains unchanged with `VITE_PILOT_OIDC_ENABLED=false`.
- No pilot release approval from unit/integration tests alone.
