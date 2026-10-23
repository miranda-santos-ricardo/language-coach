"""Step 5.4b.11: pinned-algorithm offline JWKS verification for assessment routes.

Host-provided keys MUST come from a trusted, securely refreshed OIDC JWKS feed.
This adapter never fetches network resources, mints tokens, trusts token URLs,
or reads user identity from headers other than the verified Bearer credential.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping
from uuid import UUID

import jwt

from app.api.conversation_assessment_auth import VerifiedIdentity


class TokenRejected(Exception):
    """Public-safe token rejection; do not reveal verification details."""


@dataclass(frozen=True)
class OIDCVerifierConfig:
    issuer: str
    audience: str
    allowed_algorithm: str = "RS256"
    leeway_seconds: int = 30
    max_token_lifetime_seconds: int = 3600
    admin_scope: str = "conversation:assessment:reconcile"
    required_admin_acr: str = ""  # mandatory non-empty at admin-capable verifier configuration


class AssessmentOIDCVerifier:
    def __init__(
        self,
        *,
        config: OIDCVerifierConfig,
        public_keys_by_kid: Mapping[str, str],
        account_is_active: Callable[[UUID], bool],
        token_is_revoked: Callable[[str], bool],
    ) -> None:
        if (not isinstance(config, OIDCVerifierConfig)
                or not config.issuer.startswith("https://")
                or not config.audience.strip()
                or config.allowed_algorithm not in ("RS256", "ES256")
                or not 0 <= config.leeway_seconds <= 120
                or not 60 <= config.max_token_lifetime_seconds <= 86400
                or not isinstance(public_keys_by_kid, Mapping)
                or not public_keys_by_kid
                or not all(type(k) is str and k and type(v) is str and v for k, v in public_keys_by_kid.items())
                or not callable(account_is_active) or not callable(token_is_revoked)):
            raise ValueError("Secure OIDC verification configuration required")
        self.config = config
        self.keys = dict(public_keys_by_kid)
        self.account_is_active = account_is_active
        self.token_is_revoked = token_is_revoked

    def __call__(self, token: str) -> VerifiedIdentity:
        try:
            if type(token) is not str or not token or len(token) > 16384:
                raise TokenRejected()
            header = jwt.get_unverified_header(token)
            if header.get("alg") != self.config.allowed_algorithm:
                raise TokenRejected()
            kid = header.get("kid")
            if type(kid) is not str or kid not in self.keys:
                raise TokenRejected()
            # No jku, x5u, jwk, key discovery, or algorithm negotiation from token.
            if any(k in header for k in ("jku", "x5u", "jwk")):
                raise TokenRejected()
            claims = jwt.decode(
                token,
                self.keys[kid],
                algorithms=[self.config.allowed_algorithm],
                issuer=self.config.issuer,
                audience=self.config.audience,
                leeway=self.config.leeway_seconds,
                options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub", "jti"]},
            )
            now = datetime.now(timezone.utc).timestamp()
            if (type(claims["iat"]) not in (int, float)
                    or type(claims["exp"]) not in (int, float)
                    or claims["iat"] > now + self.config.leeway_seconds
                    or claims["exp"] - claims["iat"] > self.config.max_token_lifetime_seconds
                    or type(claims["jti"]) is not str or not claims["jti"]):
                raise TokenRejected()
            subject = claims["sub"]
            if type(subject) is not str:
                raise TokenRejected()
            user_id = UUID(subject)
            if str(user_id) != subject.lower():
                raise TokenRejected()
            raw_scopes = claims.get("scope")
            if type(raw_scopes) is not str:
                raise TokenRejected()
            scopes = frozenset(raw_scopes.split())
            if not scopes or any(not x for x in scopes):
                raise TokenRejected()
            if self.config.admin_scope in scopes:
                if not self.config.required_admin_acr or claims.get("acr") != self.config.required_admin_acr:
                    raise TokenRejected()
            if self.token_is_revoked(claims["jti"]) or self.account_is_active(user_id) is not True:
                raise TokenRejected()
            return VerifiedIdentity(user_id=user_id, active=True, scopes=scopes)
        except Exception:
            raise TokenRejected("Authentication required") from None
