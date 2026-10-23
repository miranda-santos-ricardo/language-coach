# Phase 7 — Step 5.4b.10: Operational Readiness & Secure Activation

## Intent and scope
This is a **diagnostic, fail-closed readiness gate**, not automatic route activation.
No existing app files/routes are changed; no migrations, secrets, or new dependencies.

### Gates
- Required integration callbacks must be explicitly supplied.
- PostgreSQL must be reachable; Alembic must report `c5202603` and both execution/reconciliation tables must exist.
- Ten operational attestations must be explicitly recorded. These are **human statements**, not independently verified outcomes.
- Missing, inaccessible, stale, or uncertain checks produce `NO_GO`.

### Important distinction
A `GO` report reflects successful diagnostics **plus** operator attestations. It does not by itself prove JWT signature verification, issuer/audience, MFA, rate limiting, disaster recovery, observability, a PostgreSQL concurrency test run, or provider idempotence. Preserve the routes as disabled until relevant real-world checks are evidenced and approved. Do not copy unchecked attestations merely to obtain GO.

### Remaining blockers from Step 5.4b.8
The two PostgreSQL integration tests remain unverified until run against an isolated migrated PostgreSQL test database with independent connections. The user last reported `2 skipped`; do not treat as passed.

### Usage example (never hard-code secrets)
```python
from app.services.assessment_activation_readiness import (
    evaluate_assessment_readiness, OperationalAttestations,
)
from sqlalchemy import create_engine

# Use a secure, externally configured DSN and a read-only inspection credential.
engine = create_engine(configured_dsn)
report = evaluate_assessment_readiness(
    database_connection_factory=engine.connect,
    token_verifier=app_token_verifier,
    evaluator=model_call,
    request_session_dependency=db_dependency,
    ledger_session_factory=ledger_session_factory,
    context_from_session=context_from_session,
    attestations=OperationalAttestations(),  # NO_GO until independent controls verified
)
print(report.verdict, report.blockers)
```

### Validation
From `backend`:
```powershell
python -m pytest -q tests/test_assessment_activation_readiness.py
python -m pytest -q
alembic current
```
Baseline before package: 779 passed, 2 skipped for Step 5.4b.8; Step 5.4b.9 expected to add 10 (789 passed, 2 skipped), but user did not report its local results yet. With these 12 new tests, **801 passed, 2 skipped** is conditional on 5.4b.9 being installed and otherwise passing. Expected head `c5202603 (head)`.

### Activation policy
1. Run pending PostgreSQL tests in a dedicated disposable DB; keep their results as CI evidence.
2. Configure real token signature, issuer, audience, expiry, and account state checks, plus MFA for admins.
3. Verify per-user authorization, rate limits, bounded LLM costs, provider timeouts, data minimization/retention, audit logging, runbooks and rollback.
4. Review all findings. A separate deployment decision controls registration of the opt-in assessment and admin routes.

No automated deployment or installation function is provided in this step.
