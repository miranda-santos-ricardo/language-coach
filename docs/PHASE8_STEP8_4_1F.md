# Phase 8 — Step 8.4.1f: External OIDC Runtime Integration

## Objective
Connect the external OIDC identity-link resolver from Step 8.4.1e to the isolated guarded learner app from Step 8.4.1c. No automatic deployment or changes to the legacy local application.

## Added
- `backend/app/services/learner_external_oidc_runtime.py`: explicit opt-in app factory requiring issuer/audience/keys, a DB session factory, token revocation and account-status callbacks.
- `backend/tests/test_learner_external_oidc_runtime.py`: signed RS256 JWT tests against a temporary DB, including cross-user access, revoked links, missing links, inactive users, invalid claims, and datastore failure.

## Trust boundaries
1. Host supplies pinned trusted OIDC keys; **no** token-driven JWKS lookup.
2. `ExternalOIDCLearnerVerifier` validates signed JWT and scope, checks JTI revocation, resolves active `(issuer, sub)` in persistent storage, then verifies active internal account.
3. `oidc_learner_adapter` translates only the verified identity type.
4. `LearnerRouteGuard` rejects cross-user paths before existing FastAPI services run.
5. The original `app.main` and frontend are unchanged. Pilot app must be deployed **instead of**, not alongside, legacy unrestricted routes.

## Windows validation
From `backend`:

```powershell
python -m pytest -q tests/test_learner_external_oidc_runtime.py
python -m pytest -q tests/test_learner_identity.py tests/test_learner_route_guard.py tests/test_learner_pilot_routes.py tests/test_learner_oidc_bootstrap.py tests/test_learner_external_identity.py tests/test_learner_external_oidc_runtime.py
python -m pytest -q
python -m alembic current
```

From `frontend`:

```powershell
npm test -- --run
npm run build
```

## Out of scope / unresolved
- Real external IdP JWKS retrieval/refresh, key rollover, login/logout via Authorization Code + PKCE, frontend token management.
- Operator-only provisioning/revocation API, operator MFA and audit trail.
- PostgreSQL concurrent linking proof, migrations against a running PostgreSQL instance and operational fault injection.
- Rate limits, retention, informed consent and end-user pilot release gates.
- Explicit production deployment configuration; creating the factory alone must never activate the pilot.

## Acceptance
The dedicated tests, existing suites and build pass in Windows; no unprotected legacy routes are mounted on the isolated pilot app; no untrusted claims authorize a user; database failures fail closed. **Passing tests does not mean `PILOT_READY`.**
