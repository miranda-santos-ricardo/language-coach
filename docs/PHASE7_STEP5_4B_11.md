# Phase 7 — Step 5.4b.11 — Production Identity Integration & Activation Validation

## Scope
Optional offline asymmetric OIDC/JWT verifier compatible with the existing `VerifiedIdentity` and assessment/admin installers. **No automatic endpoint activation.**

- Pins issuer, audience, algorithm (`RS256` or `ES256`), and configured `kid` public keys.
- Requires `exp`, `iat`, `nbf`, `iss`, `aud`, `sub`, `jti`; limits max token lifetime.
- Checks account active and token revocation through **trusted, fail-closed injected callbacks**.
- Requires matching `acr` on admin-scoped credentials, but deployment must separately establish that its identity provider actually enforces MFA.
- Never downloads JWKS from token-supplied URLs, never accepts unsigned/HMAC tokens or client `X-User-Id`.
- Does not implement a JWKS refresh pipeline, introspection, OIDC discovery, identity-provider onboarding, account storage, route activation or token issuance.

## Integration (not activation)

```python
from app.services.assessment_oidc_verifier import AssessmentOIDCVerifier, OIDCVerifierConfig
verifier = AssessmentOIDCVerifier(
    config=OIDCVerifierConfig(
        issuer="https://trusted-issuer.example/",
        audience="language-coach-api",
        required_admin_acr="your-idp-mfa-acr-value",
    ),
    public_keys_by_kid={"current-kid": trusted_public_key_pem},
    account_is_active=check_current_local_account,
    token_is_revoked=check_revocation_database,
)
# Pass verifier into installers ONLY after operational readiness review.
```

Do not treat a token's `sub` as a local user UUID if your identity provider uses opaque subject identifiers. In that situation implement an explicit trusted `(iss, sub) -> local UUID` mapping before integrating this verifier. The current adapter intentionally rejects non-UUID subjects.

## Dependencies
Add `PyJWT[crypto]>=2.8,<3` to the backend's locked dependency declaration before installation, subject to your project's dependency management. Tests additionally use `cryptography`.

## Validation

```powershell
python -m pytest -q tests/test_assessment_oidc_verifier.py
python -m pytest -q
alembic current
```

Expected migration: `c5202603 (head)`. This step adds no migrations.

## No-go remains
The prior two PostgreSQL concurrency tests must run against a disposable PostgreSQL database. A configured IdP must be tested for real token signature, issuer, audience, expiry, key rotation, MFA and account deactivation. Operational readiness attestation, provider budgets and monitoring remain required. No routes automatically mounted.
