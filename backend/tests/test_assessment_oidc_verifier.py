from datetime import datetime, timezone
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.services.assessment_oidc_verifier import AssessmentOIDCVerifier, OIDCVerifierConfig, TokenRejected


@pytest.fixture
def fixture():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    active = {"value": True}
    revoked = set()
    config = OIDCVerifierConfig(issuer="https://id.example.test/", audience="language-coach-api", required_admin_acr="mfa")
    verifier = AssessmentOIDCVerifier(config=config, public_keys_by_kid={"a": pub},
        account_is_active=lambda uid: active["value"], token_is_revoked=lambda jti: jti in revoked)
    now = int(datetime.now(timezone.utc).timestamp())
    base = dict(iss=config.issuer, aud=config.audience, sub=str(uuid4()), exp=now+600, nbf=now-1,
                iat=now-1, jti="unique-jti", scope="conversation:assess")
    def sign(**changes):
        data = dict(base)
        data.update(changes)
        return jwt.encode(data, private, algorithm="RS256", headers={"kid":"a"})
    return verifier, sign, active, revoked, base


def test_valid_user(fixture):
    verifier, sign, *_ = fixture
    identity = verifier(sign())
    assert "conversation:assess" in identity.scopes and identity.active


def test_valid_admin_with_mfa(fixture):
    verifier, sign, *_ = fixture
    assert "conversation:assessment:reconcile" in verifier(sign(scope="conversation:assessment:reconcile", acr="mfa")).scopes

@pytest.mark.parametrize("changes", [
    {"iss":"https://evil.test/"}, {"aud":"other"}, {"exp":1}, {"nbf":9999999999},
    {"iat":9999999999}, {"sub":"not-a-uuid"}, {"scope":123},
    {"jti":""}, {"exp":9999999999},
    {"scope":"conversation:assessment:reconcile"},
    {"scope":"conversation:assessment:reconcile", "acr":"password"},
])
def test_rejected_claims(fixture, changes):
    verifier, sign, *_ = fixture
    with pytest.raises(TokenRejected): verifier(sign(**changes))


def test_revoke(fixture):
    verifier, sign, _, revoked, _ = fixture
    revoked.add("unique-jti")
    with pytest.raises(TokenRejected): verifier(sign())


def test_inactive(fixture):
    verifier, sign, active, *_ = fixture
    active["value"] = False
    with pytest.raises(TokenRejected): verifier(sign())


def test_unknown_kid(fixture):
    verifier, sign, *_ = fixture
    # Re-sign a token using a different key identifier by extending fixture sign signature in place.
    token = sign()
    parts = token.split('.')
    import base64, json
    header = json.loads(base64.urlsafe_b64decode(parts[0]+'=='))
    header['kid']='unknown'
    h = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b'=').decode()
    with pytest.raises(TokenRejected): verifier('.'.join([h]+parts[1:]))


def test_malformed(fixture):
    verifier, *_ = fixture
    with pytest.raises(TokenRejected): verifier('garbage')


def test_fail_closed_status_checker_exception(fixture):
    verifier, sign, *_ = fixture
    verifier.account_is_active = lambda uid: 1 / 0
    with pytest.raises(TokenRejected):
        verifier(sign())
