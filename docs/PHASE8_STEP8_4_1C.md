# Phase 8 — Step 8.4.1c: guarded learner API (opt-in)

## Scope
- Reuses existing profile, session, conversation-turn and user routers, with a shared owner guard.
- Requires a host-supplied bearer verifier returning `VerifiedLearnerIdentity` (`learner:access` scope).
- The `oidc_learner_adapter` can adapt the already-implemented `AssessmentOIDCVerifier`; it **does not** independently configure an OIDC provider.
- Blocks cross-user access before services/DB/LLM invocation, returning 404.
- Deliberately blocks `/users` list/create when using the guarded router, even with a valid token.
- Keeps the default `app.main:app` unmodified, preserving local mode. No experimental endpoint is activated.

## Files
- `backend/app/services/learner_pilot_routes.py`: reusable protected-router composition and OIDC adapter.
- `backend/app/api/learner_pilot_app.py`: isolated pilot application factory.
- `backend/tests/test_learner_pilot_routes.py`: access denial and deployment contract tests.

## Activation constraints
**Do not use this package to start a real multi-user pilot yet.** The pilot application has no production OIDC bootstrap, external JWKS refresh, user enrollment/login frontend, pilot CORS/HTTPS setup, or validated token lifecycle. The example verifier used in tests is intentionally fake and must never be deployed.

The pilot app is constructed only by explicit `create_learner_pilot_app(verify_bearer_token=...)` call and is NOT installed by the default FastAPI application. A future host bootstrap must supply the real `AssessmentOIDCVerifier` configured with trusted issuer, audience, pinned algorithms, refreshed keys, account activation and revocation callbacks; adapt it via `oidc_learner_adapter`.

**Never add this router alongside the existing unguarded `api_router`: that would leave an authentication bypass.** The factory represents an alternative isolated app. Do not deploy both apps over the same exposed backend.

Public reference endpoints (health, languages, registers) remain readable in the isolated app. Reassess their data exposure before pilot.

## PowerShell verification
From repository root, extract the ZIP keeping paths, then:

```powershell
cd backend
python -m pytest -q tests/test_learner_identity.py tests/test_learner_route_guard.py tests/test_learner_pilot_routes.py
python -m pytest -q
cd ../frontend
npm test -- --run
npm run build
```

Expected: no unauthenticated access to learner routes; 404 when bearer belongs to a different user; unscoped `/users` list/create denied; no regressions. Review test logs for skipped PostgreSQL integration tests; passing tests alone do not prove pilot readiness.

## Known remaining work
- Real identity provider, registration and token flow on the frontend.
- Repository-level tenant isolation and other owner references in request body.
- Enrollment/provisioning strategy replacing the local public user list.
- HTTPS, MFA (administrative), CORS hardening, retention, rate limits, quotas and observability.
- PostgreSQL concurrency tests and operational GO/NO_GO evidence.

## Validation in assistant runtime
`python -m compileall` and ZIP integrity checks only. Automated pytest collection could not complete due to missing environment dependencies (`psycopg` and `openai`). No passing-test result is claimed for this increment. Await user's local test results before the next step.
