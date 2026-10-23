# Phase 7 — Step 5.4b.4 Authentication & Authorization Hardening

## Scope
Add a **fail-closed** Bearer authentication boundary to the optional conversation-assessment endpoint. There is no default token verifier, no token issuer, no JWT decoding and no automatic registration. The existing SQLAlchemy resolver must still filter ownership at query time (`PracticeSession → LanguageProfile.user_id`).

## Security contract
- `verify_bearer_token(token)` **must be provided by the host** and return a `VerifiedIdentity` only after cryptographic verification of the token, issuer/audience/expiration, account state and any applicable revocation policies. Do not merely decode JWT payloads or accept plain UUIDs as credentials.
- `active=True` and `conversation:assess` scope are required.
- Never derive identity from query/body/URL or `X-User-Id`.
- Missing or rejected credentials => 401; insufficient authorization => 403.
- Other-user or missing turns must not leak existence or content; SQL resolver and endpoint remain responsible for indistinguishable denials.
- The route remains disabled by default; no modifications to `app/main.py` are included.

## How to wire when a real verifier is ready
```python
from app.api.conversation_assessment_auth import install_authenticated_assessment_endpoint, VerifiedIdentity
# Your existing authentication integration must implement verify_bearer_token.
install_authenticated_assessment_endpoint(
    app,
    enabled=True,  # ONLY after reviewing identity / DB / LLM dependencies
    verify_bearer_token=verify_bearer_token,
    context_from_session=context_from_session,
    model_call=model_call,
    session_dependency=get_db,
)
```
The verifier MUST map an external verified subject to the application's actual `LanguageProfile.user_id`, with the correct tenancy mapping.

## Validation
```powershell
python -m pytest -q tests/test_conversation_assessment_auth.py
python -m pytest -q
alembic current
```
Tests use a simulated trusted verifier and do **not** prove real-world authentication. Production activation remains blocked pending: verified auth implementation, integration tests against PostgreSQL/FastAPI with two users, CSRF/replay considerations (if cookie transport is ever added), rate limits, privacy review, and persistent cross-worker idempotency. No migrations or paid calls.
