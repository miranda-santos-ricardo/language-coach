# Step 8.4.1f — Correction: shared pilot DB dependency

## Root cause

The `ExternalOIDCLearnerVerifier` used the injected `db_session_factory` to resolve an external subject, but the preexisting `/users/{user_id}` route depended on the global `get_db` session. In tests this queried a different database and returned `404` even for a valid linked user.

## Correction

`create_external_oidc_learner_pilot_app` now overrides `get_db` only on its isolated pilot FastAPI instance, using the same session factory as the verifier. No changes are made to `app.main`, legacy routes, OIDC validation or owner authorization. A regression test asserts the override and a successful same-user lookup; existing cross-user and revoked-link assertions remain unchanged.

## Local validation (PowerShell)

From `backend`:

```powershell
python -m pytest -q tests/test_learner_external_oidc_runtime.py
python -m pytest -q
```

From `frontend`:

```powershell
npm test -- --run
npm run build
```

## Boundaries

This fixes shared persistence wiring, not live IdP integration. For production deployment, configure the factory to use the intended PostgreSQL database and still perform real PostgreSQL concurrency, operational security and authorization testing before enabling pilot use.
