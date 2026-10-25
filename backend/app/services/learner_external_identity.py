"""Phase 8.4.1e: verified OIDC subject resolution. No self-registration.

Only trusted server-side operators may call provision_link/revoke_link.
JWT validation uses pinned server-supplied keys; no token-provided URL is fetched.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Callable, Mapping
from uuid import UUID
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.oidc_identity_link import OIDCIdentityLink
from app.models.user import User
from app.services.assessment_oidc_verifier import OIDCVerifierConfig, TokenRejected
from app.api.conversation_assessment_auth import VerifiedIdentity

class LinkConflict(ValueError):
    pass

def _subject_ok(subject: str) -> bool:
    return type(subject) is str and 0 < len(subject) <= 255 and not any(ord(c) < 32 for c in subject)

def provision_link(db: Session, *, issuer: str, subject: str, user_id: UUID) -> OIDCIdentityLink:
    """Operator-only; caller must authenticate operator and authorize account linking.

    Caller owns transaction and must commit. Unique DB constraint resolves races.
    Revoked links cannot be reassigned: investigate and explicitly remediate offline.
    """
    if not issuer.startswith("https://") or len(issuer) > 512 or not _subject_ok(subject) or not isinstance(user_id, UUID):
        raise ValueError("Invalid identity link")
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("Unknown local user")
    existing = db.execute(select(OIDCIdentityLink).where(OIDCIdentityLink.issuer == issuer, OIDCIdentityLink.subject == subject)).scalar_one_or_none()
    if existing is not None:
        raise LinkConflict("Subject already linked or revoked")
    link = OIDCIdentityLink(issuer=issuer, subject=subject, user_id=user_id, is_active=True)
    db.add(link)
    db.flush()
    return link

def revoke_link(db: Session, *, issuer: str, subject: str) -> bool:
    """Operator-only; caller owns transaction. Idempotent revocation."""
    link = db.execute(select(OIDCIdentityLink).where(OIDCIdentityLink.issuer == issuer, OIDCIdentityLink.subject == subject)).scalar_one_or_none()
    if link is None or not link.is_active:
        return False
    link.is_active = False
    link.revoked_at = datetime.now(timezone.utc)
    db.flush()
    return True

class ExternalOIDCLearnerVerifier:
    def __init__(self, *, config: OIDCVerifierConfig, public_keys_by_kid: Mapping[str,str],
                 db_session_factory: Callable[[], Session], token_is_revoked: Callable[[str], bool],
                 account_is_active: Callable[[UUID], bool]):
        if (not isinstance(config, OIDCVerifierConfig) or not config.issuer.startswith("https://")
                or not config.audience or config.allowed_algorithm not in ("RS256", "ES256")
                or not 0 <= config.leeway_seconds <= 120
                or not 60 <= config.max_token_lifetime_seconds <= 86400
                or not public_keys_by_kid or not all(type(k) is str and k and type(v) is str and v for k,v in public_keys_by_kid.items())
                or not all(callable(f) for f in (db_session_factory, token_is_revoked, account_is_active))):
            raise ValueError("Trusted OIDC configuration required")
        self.config=config
        self.keys=dict(public_keys_by_kid)
        self.db_session_factory=db_session_factory
        self.token_is_revoked=token_is_revoked
        self.account_is_active=account_is_active

    def __call__(self, token: str) -> VerifiedIdentity:
        try:
            if type(token) is not str or not token or len(token)>16384:
                raise TokenRejected()
            header=jwt.get_unverified_header(token)
            if header.get("alg") != self.config.allowed_algorithm or any(k in header for k in ("jku","x5u","jwk")):
                raise TokenRejected()
            kid=header.get("kid")
            if type(kid) is not str or kid not in self.keys:
                raise TokenRejected()
            claims=jwt.decode(token, self.keys[kid], algorithms=[self.config.allowed_algorithm],
                issuer=self.config.issuer,audience=self.config.audience,leeway=self.config.leeway_seconds,
                options={"require":["exp","iat","nbf","iss","aud","sub","jti"]})
            now=datetime.now(timezone.utc).timestamp()
            if (type(claims["iat"]) not in (int,float) or type(claims["exp"]) not in (int,float)
                    or claims["iat"]>now+self.config.leeway_seconds
                    or claims["exp"]-claims["iat"]>self.config.max_token_lifetime_seconds
                    or type(claims["jti"]) is not str or not claims["jti"]
                    or not _subject_ok(claims["sub"])):
                raise TokenRejected()
            raw_scope=claims.get("scope")
            if type(raw_scope) is not str or not raw_scope.strip():
                raise TokenRejected()
            scopes=frozenset(raw_scope.split())
            if "learner:access" not in scopes or self.config.admin_scope in scopes:
                raise TokenRejected()
            if self.token_is_revoked(claims["jti"]) is not False:
                raise TokenRejected()
            with self.db_session_factory() as db:
                link=db.execute(select(OIDCIdentityLink).where(
                    OIDCIdentityLink.issuer == self.config.issuer,
                    OIDCIdentityLink.subject == claims["sub"],
                    OIDCIdentityLink.is_active.is_(True))).scalar_one_or_none()
                if link is None or db.get(User,link.user_id) is None:
                    raise TokenRejected()
                uid=link.user_id
            if self.account_is_active(uid) is not True:
                raise TokenRejected()
            return VerifiedIdentity(user_id=uid, active=True, scopes=scopes)
        except Exception:
            raise TokenRejected("Authentication required") from None
