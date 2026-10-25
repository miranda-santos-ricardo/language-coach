# Phase 8 — Step 8.4.1b (preparatory guard)

## Scope

Adds `require_learner_owner(path_user_id, authenticated_user_id)` in
`backend/app/services/learner_route_guard.py`, with five deterministic tests.
The guard accepts UUIDs only and returns HTTP 404 on an ownership mismatch.

**Security boundary:** `authenticated_user_id` MUST originate from the
server-verified `make_learner_identity_dependency`, never from URL parameters,
request body or client-supplied identity headers. The guard is a defense-in-depth
owner check, not a token verifier or a replacement for DB-scoped authorization.

## Exclusions

- No existing production/main API routes are modified or wired.
- No auth provider, token issuance, OIDC configuration, migrations or frontend changes.
- No experimental assessment endpoint is enabled.
- This increment is **not** pilot-ready multi-user authentication.

## Validation (PowerShell, from repository root)

```powershell
cd backend
python -m pytest -q tests/test_learner_identity.py tests/test_learner_route_guard.py
python -m pytest -q
cd ../frontend
npm test -- --run
npm run build
```

## Acceptance

- Valid verified owner allowed.
- Missing or bad bearer rejected before protected handler executes.
- Cross-user path hidden with 404, no handler side effects.
- Spoofed identity header cannot override verified user.
- Existing suites continue to pass.

## Next increment

Audit every user-scoped route and repository query, plan provider-backed login
and frontend token acquisition, and only then mount guards with safe migration.
