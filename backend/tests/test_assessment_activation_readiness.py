"""No credentials, internet, PostgreSQL, external LLM or paid calls needed."""
from app.services.assessment_activation_readiness import (
    EXPECTED_ALEMBIC_HEAD, REQUIRED_ATTESTATIONS,
    OperationalAttestations, evaluate_assessment_readiness,
)


def inspect(**overrides):
    args = dict(database_connection_factory=None, token_verifier=None, evaluator=None,
                request_session_dependency=None, ledger_session_factory=None,
                context_from_session=None, attestations=None)
    args.update(overrides)
    return evaluate_assessment_readiness(**args)


def test_default_no_go():
    report = inspect()
    assert report.verdict == "NO_GO"
    assert "postgresql_connection" in report.blockers


def test_no_attestation_is_implicit():
    report = inspect(token_verifier=lambda token: token)
    assert "token_signature_issuer_audience_expiry_verified" in report.blockers


def test_manual_approval_not_enough():
    report = inspect(attestations=OperationalAttestations(frozenset(REQUIRED_ATTESTATIONS)))
    assert report.verdict == "NO_GO"


def test_all_dependencies_not_enough_without_database():
    f = lambda: None
    report = inspect(token_verifier=f, evaluator=f, request_session_dependency=f,
                     ledger_session_factory=f, context_from_session=f)
    assert report.verdict == "NO_GO"


def test_bad_dialect_rejected():
    class C:
        dialect = type("D", (), {"name": "sqlite"})()
        def __enter__(self): return self
        def __exit__(self, *a): pass
    report = inspect(database_connection_factory=lambda: C())
    assert "postgresql_connection" in report.blockers


def test_db_failure_no_exception_or_secret():
    def connection(): raise RuntimeError("secret-password")
    report = inspect(database_connection_factory=connection)
    assert report.verdict == "NO_GO"
    assert "secret-password" not in repr(report)


def test_bad_attestation_type_fail_closed():
    report = inspect(attestations={"approved": REQUIRED_ATTESTATIONS})
    assert all(not f.passed for f in report.findings if f.check in REQUIRED_ATTESTATIONS)


def test_unknown_attestation_does_not_bypass():
    report = inspect(attestations=OperationalAttestations(frozenset({"everything_ok"})))
    assert report.verdict == "NO_GO"


def test_blockers_are_consistent():
    report = inspect()
    assert len(report.blockers) == sum(not f.passed for f in report.findings)


def test_expected_migration():
    assert EXPECTED_ALEMBIC_HEAD == "c5202603"


def test_no_duplicate_check_identifiers():
    report = inspect()
    assert len({f.check for f in report.findings}) == len(report.findings)


def test_no_enablement_side_effects():
    assert not hasattr(inspect(), "install_router")
