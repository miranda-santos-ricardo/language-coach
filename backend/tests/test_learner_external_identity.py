from datetime import datetime, timezone
from uuid import uuid4
import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from app.db.base import Base
from app.models.user import User
from app.models.oidc_identity_link import OIDCIdentityLink
from app.services.learner_external_identity import provision_link, revoke_link, LinkConflict, ExternalOIDCLearnerVerifier
from app.services.assessment_oidc_verifier import OIDCVerifierConfig, TokenRejected

@pytest.fixture
def setup():
    engine=create_engine("sqlite+pysqlite:///:memory:",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    u=uuid4(); v=uuid4()
    with Session(engine) as db:
        db.add_all([User(id=u,display_name="A"),User(id=v,display_name="B")]);db.commit()
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    public=private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    config=OIDCVerifierConfig(issuer="https://id.example.test/",audience="pilot-api")
    revoked=set()
    verifier=ExternalOIDCLearnerVerifier(config=config,public_keys_by_kid={"main":public},
        db_session_factory=lambda:Session(engine), token_is_revoked=lambda j: j in revoked,
        account_is_active=lambda uid: uid in (u,v))
    now=int(datetime.now(timezone.utc).timestamp())
    def sign(**changes):
        d=dict(iss=config.issuer,aud=config.audience,sub="opaque|person-42",iat=now,nbf=now-1,
               exp=now+600,jti="token-1",scope="learner:access")
        d.update(changes)
        return jwt.encode(d,private,algorithm="RS256",headers={"kid":"main"})
    yield engine,u,v,verifier,sign,revoked
    engine.dispose()

def test_explicit_link_and_revocation(setup):
    engine,u,_,verify,sign,_=setup
    with pytest.raises(TokenRejected):verify(sign())
    with Session(engine) as db:
        provision_link(db,issuer="https://id.example.test/",subject="opaque|person-42",user_id=u)
        db.commit()
    assert verify(sign()).user_id == u
    with Session(engine) as db:
        assert revoke_link(db,issuer="https://id.example.test/",subject="opaque|person-42")
        db.commit()
    with pytest.raises(TokenRejected):verify(sign())

def test_no_rebinding_even_revoked(setup):
    engine,u,v,_,_,_=setup
    with Session(engine) as db:
        provision_link(db,issuer="https://id.example.test/",subject="opaque|person-42",user_id=u)
        db.commit()
    with Session(engine) as db:
        with pytest.raises(LinkConflict):provision_link(db,issuer="https://id.example.test/",subject="opaque|person-42",user_id=v)
        assert revoke_link(db,issuer="https://id.example.test/",subject="opaque|person-42")
        db.commit()
    with Session(engine) as db:
        with pytest.raises(LinkConflict):provision_link(db,issuer="https://id.example.test/",subject="opaque|person-42",user_id=v)

def test_no_automatic_link_by_email_or_uuid(setup):
    _,_,_,verify,sign,_=setup
    with pytest.raises(TokenRejected):verify(sign(email="a@example.com"))

def test_reject_wrong_issuer_and_scope(setup):
    engine,u,_,verify,sign,_=setup
    with Session(engine) as db:
        provision_link(db,issuer="https://id.example.test/",subject="opaque|person-42",user_id=u)
        db.commit()
    for claims in ({"iss":"https://other.example/"},{"scope":"other"},{"exp":1},{"sub":"unlinked"}):
        with pytest.raises(TokenRejected):verify(sign(**claims))

def test_revoked_jti(setup):
    engine,u,_,verify,sign,revoked=setup
    with Session(engine) as db:
        provision_link(db,issuer="https://id.example.test/",subject="opaque|person-42",user_id=u)
        db.commit()
    revoked.add("token-1")
    with pytest.raises(TokenRejected):verify(sign())
