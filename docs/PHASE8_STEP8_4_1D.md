# Phase 8 — Step 8.4.1d: OIDC Pilot Bootstrap (offline pinned keys)

## Scope

This increment wires the existing Phase 7 `AssessmentOIDCVerifier` into the
opt-in learner pilot app from 8.4.1c. It does **not** enable the pilot in
`app.main`, add new routes to the default app, implement a browser auth flow,
or claim certification with a real identity provider.

The host explicitly supplies an HTTPS issuer, audience, pinned public PEM keys
indexed by `kid`, active-account lookup and revocation lookup. The existing
verifier validates signature, pinned algorithm, issuer, audience, exp, iat,
nbf, jti, maximum lifetime, UUID subject, revocation and account activity.
The learner dependency independently requires `learner:access`. Tokens are never
logged or persisted by this integration. No network calls or paid APIs.

## Files

- `backend/app/services/learner_oidc_bootstrap.py` (new)
- `backend/tests/test_learner_oidc_bootstrap.py` (new)

## Production limitations and blocking work

- **Real identity provider not connected or validated.** Do not mark pilot ready.
- **External OIDC subjects not supported yet.** Phase 7 verifier requires the
  `sub` claim to be the canonical UUID of the internal user. The host must
  NOT rewrite a token's subject, use email as a subject, or silently authorize
  a user by route ID. Plan an explicit persistent `(issuer, sub) -> user UUID`
  binding after subject verification, with account lifecycle and collision tests.
- Trust anchor refresh/rotation and JWKS retrieval **are host responsibilities**.
  Never trust JWKS URLs read from tokens. Document secure retrieval, rotation,
  outages and last-known-good key expiry before a real pilot.
- `account_is_active` and `token_is_revoked` callbacks must query authoritative
  stores and fail closed on errors. Do not deploy permissive lambdas from tests.
- Do not expose the legacy default app simultaneously with the protected pilot
  API on the same public origin. Complete route coverage, user bootstrap, CORS,
  CSRF if cookies are later adopted, TLS, browser Authorization Code + PKCE,
  storage strategy, logout and revocation lifecycle before external users.
- Real MFA and operational observability still pending.

## Validation (PowerShell from repository root)

```powershell
cd backend
python -m pytest -q tests/test_learner_identity.py tests/test_learner_route_guard.py tests/test_learner_pilot_routes.py tests/test_learner_oidc_bootstrap.py
python -m pytest -q
cd ../frontend
npm test -- --run
npm run build
```

## Acceptance

Tests must reject missing/invalid, mismatched audience/issuer, missing learner
scope, revoked, inactive, forged and non-UUID-subject tokens; refuse absent
bootstrap config; deny cross-user requests before DB access. Maintain disabled
by default and no code changes to `app.main`. User executes suite and confirms.
