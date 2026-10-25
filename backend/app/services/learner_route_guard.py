"""Phase 8.4.1b preparatory owner guard; NOT installed on routers by default.

The authenticated UUID must come from make_learner_identity_dependency,
never from the request path or unverified headers. Fail closed on mismatch.
"""
from __future__ import annotations

from uuid import UUID
from fastapi import HTTPException


def require_learner_owner(path_user_id: UUID, authenticated_user_id: UUID) -> UUID:
    """Return authenticated owner only if route is scoped to that owner.

    A 404 rather than 403 avoids confirming the existence of other accounts.
    This check is complementary to repository-level access control.
    """
    if type(path_user_id) is not UUID or type(authenticated_user_id) is not UUID:
        raise HTTPException(status_code=404, detail="Not found")
    if path_user_id != authenticated_user_id:
        raise HTTPException(status_code=404, detail="Not found")
    return authenticated_user_id
