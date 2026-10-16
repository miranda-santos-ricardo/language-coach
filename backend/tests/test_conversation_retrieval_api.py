"""Step 7.2: HTTP read contracts using a real temporary relational database.

Only POST uses a fake LLM; GET never requires the provider.
"""
from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.main import app
from app.models import SessionStatus
from app.services.conversation_api_dependencies import get_conversation_service, get_conversation_read_service
from app.services.conversation_service import ConversationService
from app.services.conversation_read_service import ConversationReadService
from tests.test_conversation_context_integration import create_case
from tests.test_conversation_service import FakeLLM


def path(u, p, s):
    return f"/users/{u.id}/language-profiles/{p.id}/sessions/{s.id}/turns"


def add_turn(api_client, u, p, s, text="Bonjour"):
    reply = api_client.post(path(u, p, s), json={
        "text": text, "input_modality": "text", "client_request_id": str(uuid.uuid4()),
    })
    assert reply.status_code == 201, reply.text
    return reply.json()


@pytest.fixture
def seeded_api(api_client, service_session):
    provider = FakeLLM()
    app.dependency_overrides[get_conversation_service] = lambda: ConversationService(llm=provider)
    try:
        yield api_client, service_session, provider
    finally:
        app.dependency_overrides.pop(get_conversation_service, None)


def test_empty_owned_history_and_unknown_context(seeded_api):
    client, db, _ = seeded_api
    u,p,s=create_case(db)
    response=client.get(path(u,p,s))
    assert response.status_code==200 and response.json()=={"items":[],"limit":50,"offset":0}
    assert client.get(path(u,p,s).replace(str(u.id),str(uuid.uuid4()))).status_code==404


def test_list_order_pagination_and_feedback(seeded_api):
    client,db,provider=seeded_api
    u,p,s=create_case(db)
    sent=[add_turn(client,u,p,s,f"Bonjour {i}") for i in range(3)]
    page=client.get(path(u,p,s),params={"limit":2,"offset":1})
    assert page.status_code==200, page.text
    data=page.json()
    assert [row["turn_id"] for row in data["items"]] == [sent[1]["turn_id"],sent[2]["turn_id"]]
    assert data["limit"]==2 and data["offset"]==1
    assert data["items"][0]["feedback"]["grammar"]["status"]=="correct"
    assert "register" in data["items"][0]["feedback"]
    assert "register_feedback" not in data["items"][0]["feedback"]
    assert data["items"][0]["created_at"]
    assert len(provider.calls)==3  # reads must not call LLM


def test_turn_detail_and_not_found(seeded_api):
    client, db, _=seeded_api
    u,p,s=create_case(db)
    sent=add_turn(client,u,p,s)
    response=client.get(path(u,p,s)+"/"+sent["turn_id"])
    assert response.status_code==200
    assert response.json()["learner_text"]=="Bonjour"
    assert response.json()["coach_response"]==sent["coach_response"]
    assert response.json()["feedback"]==sent["feedback"]
    assert client.get(path(u,p,s)+"/"+str(uuid.uuid4())).status_code==404


def test_cross_user_profile_and_session_isolation(seeded_api):
    client,db,_=seeded_api
    u,p,s=create_case(db)
    u2,p2,s2=create_case(db)
    sent=add_turn(client,u,p,s)
    for wrong in [path(u2,p,s),path(u,p2,s),path(u,p,s2)]:
        assert client.get(wrong).status_code==404
        assert client.get(wrong+"/"+sent["turn_id"]).status_code==404
    assert client.get(path(u2,p2,s2)).json()["items"]==[]
    assert client.get(path(u2,p2,s2)+"/"+sent["turn_id"]).status_code==404


def test_completed_sessions_remain_readable(seeded_api):
    client,db,_=seeded_api
    u,p,s=create_case(db)
    sent=add_turn(client,u,p,s)
    s.status=SessionStatus.COMPLETED
    s.ended_at=datetime.now(timezone.utc)
    db.commit()
    assert client.get(path(u,p,s)).status_code==200
    assert client.get(path(u,p,s)+"/"+sent["turn_id"]).status_code==200


@pytest.mark.parametrize("params", [
    {"limit":0},{"limit":101},{"limit":-1},{"offset":-1},
    {"limit":"abc"},{"offset":"abc"},
])
def test_invalid_pagination_is_422(seeded_api, params):
    client,db,_=seeded_api
    u,p,s=create_case(db)
    assert client.get(path(u,p,s),params=params).status_code==422


def test_invalid_uuid_is_422(seeded_api):
    client,db,_=seeded_api
    u,p,s=create_case(db)
    assert client.get(path(u,p,s)+"/not-a-uuid").status_code==422


def test_read_service_is_not_llm_dependent(seeded_api):
    client,db,_=seeded_api
    u,p,s=create_case(db)
    def fail_if_called():
        raise AssertionError("LLM provider must not be constructed for GET")
    app.dependency_overrides[get_conversation_service]=fail_if_called
    assert client.get(path(u,p,s)).status_code==200


def test_sanitized_persistence_error(seeded_api):
    client,db,_=seeded_api
    u,p,s=create_case(db)
    class Broken:
        def list_turns(self, **_):
            raise OperationalError("private SQL connection", {}, Exception("secret"))
    app.dependency_overrides[get_conversation_read_service]=lambda:Broken()
    try:
        r=client.get(path(u,p,s))
        assert r.status_code==503 and "secret" not in r.text and "private" not in r.text
    finally:
        app.dependency_overrides.pop(get_conversation_read_service,None)
