# Phase 8 — Step 8.4.1e: External Identity Mapping

## Scope

Adds a database-backed, explicitly provisioned mapping `(issuer, sub) -> internal user UUID`.
No e-mail matching, implicit account creation, self-registration, login/logout UI, or automatic integration into the running app.

## Files

- `backend/app/models/oidc_identity_link.py`
- `backend/alembic/versions/c5202604_oidc_identity_links.py`
- `backend/app/services/learner_external_identity.py`
- `backend/tests/test_learner_external_identity.py`

## Controls

- Unique `(issuer, subject)` database constraint; cannot reassign a revoked subject via ordinary provisioning.
- Linking/revocation are **not exposed as API endpoints**; trusted, authenticated administrative orchestration must enforce operator authorization and audit the action before these methods are usable operationally.
- Existing learner main app and experimental endpoints are unchanged and remain opt-in/disabled.
- Verification requires pinned trusted keys, issuer/audience/signature/expiration, an exact external subject link, the learner scope, token revocation and active local account callback.
- Any lookup failure rejects the credential; token bodies and keys are not persisted here.

## Validation (PowerShell, repository root)

```powershell
cd backend
python -m alembic upgrade head
python -m alembic current
python -m pytest -q tests/test_learner_external_identity.py
python -m pytest -q
cd ../frontend
npm test -- --run
npm run build
```

## Additional release gates

- PostgreSQL concurrent provision race test, migration upgrade/downgrade rehearsal and authority-controlled linking workflow.
- Real trusted JWKS rotation/revocation feed and external IdP integration.
- Active-user determination must use authoritative account state (existing `User` only has display_name).
- PKCE code-flow frontend integration, CSRF/session protection, logout lifecycle and final deployment review.
- Revoked links are deliberately non-reassignable; remediation must be a separately audited administrator procedure.

**Not PILOT_READY / PRODUCTION_READY.** Stop after user confirmation of tests.
