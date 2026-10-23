"""Step 5.4b.10: fail-closed *diagnostic* gate; never installs routes.

The report is not a security certification. Human attestations are kept
separate from machine-verifiable checks. A GO verdict requires both.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

EXPECTED_ALEMBIC_HEAD = "c5202603"
REQUIRED_ATTESTATIONS = (
    "token_signature_issuer_audience_expiry_verified",
    "token_revocation_and_account_status_policy_verified",
    "least_privilege_scopes_and_admin_mfa_verified",
    "rate_limit_and_llm_budget_enforced",
    "provider_timeout_and_circuit_breaker_verified",
    "data_retention_and_deletion_policy_approved",
    "audit_access_controls_and_monitoring_verified",
    "postgres_concurrency_tests_passed",
    "incident_recovery_runbook_approved",
    "rollback_and_backup_tested",
)


@dataclass(frozen=True)
class ReadinessFinding:
    check: str
    passed: bool
    explanation: str
    evidence_kind: str  # measured | attested | missing


@dataclass(frozen=True)
class ReadinessReport:
    verdict: str  # GO | NO_GO
    findings: tuple[ReadinessFinding, ...]

    @property
    def blockers(self) -> tuple[str, ...]:
        return tuple(f.check for f in self.findings if not f.passed)


@dataclass(frozen=True)
class OperationalAttestations:
    """Explicit operator assertions, not automatically verified facts."""
    approved: frozenset[str] = frozenset()


def evaluate_assessment_readiness(
    *,
    database_connection_factory: Callable | None,
    token_verifier: Callable | None,
    evaluator: Callable | None,
    request_session_dependency: Callable | None,
    ledger_session_factory: Callable | None,
    context_from_session: Callable | None,
    attestations: OperationalAttestations | None = None,
) -> ReadinessReport:
    """Inspect live DB when provided; default to NO_GO for all unknowns.

    A caller must NEVER interpret this function as registering routes, validating
    a JWT cryptographically, running concurrency tests, or enforcing rate limits.
    Database checks use a connection closed by context manager.
    """
    results: list[ReadinessFinding] = []

    def add(key: str, ok: bool, description: str, kind: str) -> None:
        results.append(ReadinessFinding(key, ok, description, kind if ok else "missing"))

    dependencies = {
        "trusted_token_verifier_supplied": token_verifier,
        "model_evaluator_supplied": evaluator,
        "request_db_dependency_supplied": request_session_dependency,
        "independent_ledger_factory_supplied": ledger_session_factory,
        "trusted_context_resolver_supplied": context_from_session,
    }
    for key, dep in dependencies.items():
        add(key, callable(dep), "Callable supplied; behavior not cryptographically verified", "measured")

    if not callable(database_connection_factory):
        add("postgresql_connection", False, "No database connection probe configured", "missing")
        add("alembic_head", False, "Migration not verified", "missing")
        add("assessment_tables", False, "Database schema not verified", "missing")
    else:
        try:
            with database_connection_factory() as connection:
                if connection.dialect.name != "postgresql":
                    add("postgresql_connection", False, "Expected PostgreSQL dialect", "missing")
                    add("alembic_head", False, "Migration only checked on PostgreSQL", "missing")
                    add("assessment_tables", False, "Schema only checked on PostgreSQL", "missing")
                else:
                    from sqlalchemy import inspect, text
                    add("postgresql_connection", True, "Live PostgreSQL connection established", "measured")
                    version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                    add("alembic_head", version == EXPECTED_ALEMBIC_HEAD,
                        f"Observed {version}; required {EXPECTED_ALEMBIC_HEAD}", "measured")
                    tables = set(inspect(connection).get_table_names())
                    required = {"conversation_assessment_executions", "conversation_assessment_reconciliation_events"}
                    add("assessment_tables", required.issubset(tables),
                        "Expected execution and reconciliation tables present", "measured")
        except Exception:
            # Do not leak credentials or DSN in diagnostics.
            if not any(f.check == "postgresql_connection" for f in results):
                add("postgresql_connection", False, "Database probe failed", "missing")
            if not any(f.check == "alembic_head" for f in results):
                add("alembic_head", False, "Migration could not be verified", "missing")
            if not any(f.check == "assessment_tables" for f in results):
                add("assessment_tables", False, "Schema could not be verified", "missing")

    approved = attestations.approved if type(attestations) is OperationalAttestations else frozenset()
    for check in REQUIRED_ATTESTATIONS:
        add(check, check in approved, "Operator attestation; independent evidence required", "attested")
    return ReadinessReport("GO" if all(x.passed for x in results) else "NO_GO", tuple(results))
