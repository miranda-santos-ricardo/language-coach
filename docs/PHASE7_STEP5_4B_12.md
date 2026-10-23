# Phase 7 — Step 5.4b.12: End-to-End Identity & Secure Activation Assembly

## Scope

An explicit opt-in assembler connects Step 5.4b.11's concrete `AssessmentOIDCVerifier` to the persistent assessment route (5.4b.7) and administrative reconciliation route (5.4b.9). It fails closed without a full Step 5.4b.10 readiness report or required dependencies. No route is mounted unless `enabled=True`.

**The assembler does not automatically enable either route**, provision an OIDC provider, fetch/refresh JWKS, resolve external opaque subjects, test PostgreSQL, implement rate limiting, or certify a production deployment.

## Files

- `backend/app/api/assessment_secure_activation.py` — optional install and preflight
- `backend/tests/test_assessment_secure_activation.py` — 11 HTTP/configuration tests using signed RS256 JWTs and SQLite schema doubles; no external API requests

## Security properties

- Reject missing, incomplete, duplicated, or blocked readiness findings. Required technical findings must have `measured` provenance, operational attestations require `attested` provenance.
- Require `AssessmentOIDCVerifier`, not an arbitrary token-to-user callback.
- Use the same verifier for both routes; scopes remain separated (`conversation:assess` vs `conversation:assessment:reconcile`).
- Existing verifier checks signature/issuer/audience/expiry, revocation/account status, and `acr` for admin scope.
- Reject second route registration.
- `GO` readiness is **not** proof of measured production safety. The diagnostic accepts operator attestations; it does not verify their truth. Deployment must review evidence separately.
- The two PostgreSQL concurrency tests from 5.4b.8 still require a disposable migrated PostgreSQL test database and are NOT covered by these tests.

## Validation (backend)

```powershell
python -m pytest -q tests/test_assessment_secure_activation.py
python -m pytest -q
alembic current
```

Expected new tests: **11 passed**. Last user-reported result for 5.4b.11 said all previous tests passed but did not specify a count; do not treat any projected suite count as verified.

PostgreSQL opt-in:

```powershell
$env:ASSESSMENT_TEST_POSTGRES_URL = "postgresql+psycopg://USER:PASSWORD@localhost:5432/language_coach_test"
python -m pytest -q tests/test_postgres_assessment_concurrency.py
Remove-Item Env:ASSESSMENT_TEST_POSTGRES_URL
```

Target only a disposable, correctly migrated database. The tests are not run in the preparation environment.

## Deployment wiring contract

The caller creates a real, securely configured `AssessmentOIDCVerifier`, trusted context mapper, app request DB dependency, independent ledger factory, and real controlled model callback, then calls `evaluate_assessment_readiness(...)` against live PostgreSQL with reviewed operational attestations.

After separately reviewing evidence, the caller may explicitly call:

```python
from app.api.assessment_secure_activation import (
    SecureActivationDependencies, install_secured_assessment_routes,
)

# Application-owned dependencies; do NOT copy fake test values into production.
# report = evaluate_assessment_readiness(...)
# deps = SecureActivationDependencies(...)
# install_secured_assessment_routes(app, enabled=True, readiness=report, dependencies=deps)
```

Do not register the old endpoint installers alongside this assembler. Mount during FastAPI startup before serving traffic, not dynamically during HTTP requests.

## Still NO_GO until independently verified

- Real OIDC provider trust/JWKS rotation, revocation, user mapping
- PostgreSQL concurrency tests with separate connections
- Administrator MFA, credential and network controls
- Rate limiting, LLM budget, circuit breaker, timeouts
- Retention/deletion and audit access controls
- Backup, rollback and incident runbooks
