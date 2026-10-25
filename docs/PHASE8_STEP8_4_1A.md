# Phase 8 — Step 8.4.1a: Verified Learner Identity Contract

**Status:** Code prepared; execution on the owner's runtime and acceptance pending.

## Files created

- `backend/app/services/learner_identity.py`: identity dependency factory; uses host-injected real token verifier, requires `learner:access`, rejects missing/invalid tokens fail-closed, returns verified UUID. Does not log bearer tokens.
- `backend/tests/test_learner_identity.py`: deterministic tests for missing token, valid verified identity, forged URL user, invalid token, missing scope, inactive identity, malformed verifier response, invalid setup.

## Scope boundaries

- This is a *contract-only* increment and is **not wired to live learner routes**. Existing unprotected routes remain unprotected; do not use this code alone as justification to open the app to pilot users.
- The fake verifier exists **only in tests**. No JWT validation, OIDC provider connection, login UI, refresh flow or secure token storage is supplied here.
- All Phase 7 experimental assessment endpoints remain disabled by default and untouched.
- The business-specific `learner:access` scope is a proposed scope; confirm its issuer representation before configuring a real IdP. Assessment scope `conversation:assess` remains distinct.

## Windows PowerShell validation

```powershell
cd backend
python -m pytest -q tests/test_learner_identity.py
python -m pytest -q
cd ../frontend
npm test -- --run
npm run build
```

Record executed/skipped/passed/failed counts and environment. No LLM/API calls are made by the new unit tests.

## Acceptance

- [ ] New tests pass in developer environment.
- [ ] Existing backend tests pass without unintended regressions.
- [ ] Frontend tests and build pass.
- [ ] Confirm scope convention and pilot OIDC provider approach.
- [ ] User authorizes next incremental route-integration step.

**Decision gate:** Do not advance to 8.4.1b without test confirmation; do not claim pilot readiness.
