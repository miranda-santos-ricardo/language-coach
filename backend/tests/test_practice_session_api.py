import uuid

from fastapi.testclient import TestClient


def _create_user(
    client: TestClient,
    name: str = "Ricardo",
) -> dict:
    response = client.post(
        "/users",
        json={"display_name": name},
    )

    assert response.status_code == 201

    return response.json()


def _profile_payload(
    *,
    language_code: str = "fr",
    variant_code: str = "fr-CA",
    cefr_level: str = "B2",
    production: str = "professional",
) -> dict:
    return {
        "language_code": language_code,
        "variant_code": variant_code,
        "cefr_level": cefr_level,
        "default_production_register_code": production,
        "comprehension_register_codes": [
            "professional",
            "everyday",
            "colloquial",
        ],
    }


def _create_profile(
    client: TestClient,
    user_id: str,
    *,
    language_code: str = "fr",
    variant_code: str = "fr-CA",
    cefr_level: str = "B2",
) -> dict:
    response = client.post(
        f"/users/{user_id}/language-profiles",
        json=_profile_payload(
            language_code=language_code,
            variant_code=variant_code,
            cefr_level=cefr_level,
        ),
    )

    assert response.status_code == 201

    return response.json()


def _session_collection_url(
    user_id: str,
    profile_id: str,
) -> str:
    return (
        f"/users/{user_id}"
        f"/language-profiles/{profile_id}"
        "/sessions"
    )


def _session_detail_url(
    user_id: str,
    profile_id: str,
    practice_session_id: str,
) -> str:
    return (
        f"/users/{user_id}"
        f"/language-profiles/{profile_id}"
        f"/sessions/{practice_session_id}"
    )


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def test_create_professional_practice_session(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "formal_executive",
            "target_cefr": "C1",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["language_profile_id"] == profile["id"]

    assert body["training_mode"] == "professional"
    assert body["register"] == "formal_executive"

    assert body["profile_cefr"] == "B2"
    assert body["target_cefr"] == "C1"
    assert body["effective_cefr"] == "C1"

    assert body["language"] == "fr"
    assert body["variant"] == "fr-CA"

    assert body["scenario_key"] is None

    assert body["status"] == "active"
    assert body["started_at"] is not None
    assert body["ended_at"] is None

    assert body["created_at"] is not None
    assert body["updated_at"] is not None

    assert body["id"] is not None


def test_create_session_uses_profile_cefr_when_target_is_omitted(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "conversation",
            "register": "everyday",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["training_mode"] == "conversation"
    assert body["register"] == "everyday"

    assert body["profile_cefr"] == "B2"
    assert body["target_cefr"] is None
    assert body["effective_cefr"] == "B2"


def test_create_free_talk_session(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "free_talk",
            "register": "conversational",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["training_mode"] == "free_talk"
    assert body["register"] == "conversational"
    assert body["status"] == "active"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_create_session_rejects_invalid_training_mode(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "invalid-mode",
            "register": "professional",
        },
    )

    assert response.status_code == 422


def test_create_session_rejects_invalid_target_cefr(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "professional",
            "target_cefr": "C9",
        },
    )

    assert response.status_code == 422


def test_create_session_rejects_unknown_register(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "does_not_exist",
        },
    )

    assert response.status_code == 422


def test_create_session_rejects_unknown_user(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    response = api_client.post(
        _session_collection_url(
            str(uuid.uuid4()),
            profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "professional",
        },
    )

    assert response.status_code == 404


def test_create_session_rejects_unknown_profile(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)

    response = api_client.post(
        _session_collection_url(
            user["id"],
            str(uuid.uuid4()),
        ),
        json={
            "training_mode": "professional",
            "register": "professional",
        },
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------


def test_create_session_rejects_profile_owned_by_another_user(
    api_client: TestClient,
) -> None:
    owner = _create_user(
        api_client,
        "Owner",
    )

    other = _create_user(
        api_client,
        "Other",
    )

    profile = _create_profile(
        api_client,
        owner["id"],
    )

    response = api_client.post(
        _session_collection_url(
            other["id"],
            profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "professional",
        },
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET individual Session
# ---------------------------------------------------------------------------


def test_get_practice_session(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    create_response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "formal_executive",
            "target_cefr": "C1",
        },
    )

    assert create_response.status_code == 201

    created = create_response.json()

    response = api_client.get(
        _session_detail_url(
            user["id"],
            profile["id"],
            created["id"],
        )
    )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == created["id"]
    assert body["language_profile_id"] == profile["id"]

    assert body["training_mode"] == "professional"
    assert body["register"] == "formal_executive"

    assert body["profile_cefr"] == "B2"
    assert body["target_cefr"] == "C1"
    assert body["effective_cefr"] == "C1"

    assert body["language"] == "fr"
    assert body["variant"] == "fr-CA"

    assert body["status"] == "active"


def test_get_unknown_practice_session_returns_404(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    response = api_client.get(
        _session_detail_url(
            user["id"],
            profile["id"],
            str(uuid.uuid4()),
        )
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_practice_sessions_for_profile(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    first_response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "conversation",
            "register": "everyday",
        },
    )

    second_response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "formal_executive",
            "target_cefr": "C1",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    response = api_client.get(
        _session_collection_url(
            user["id"],
            profile["id"],
        )
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 2

    ids = {
        item["id"]
        for item in body
    }

    assert first_response.json()["id"] in ids
    assert second_response.json()["id"] in ids


def test_list_sessions_returns_only_requested_profile_sessions(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)

    french_profile = _create_profile(
        api_client,
        user["id"],
        language_code="fr",
        variant_code="fr-CA",
    )

    english_profile = _create_profile(
        api_client,
        user["id"],
        language_code="en",
        variant_code="en-CA",
        cefr_level="C1",
    )

    french_session = api_client.post(
        _session_collection_url(
            user["id"],
            french_profile["id"],
        ),
        json={
            "training_mode": "conversation",
            "register": "everyday",
        },
    )

    english_session = api_client.post(
        _session_collection_url(
            user["id"],
            english_profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "professional",
        },
    )

    assert french_session.status_code == 201
    assert english_session.status_code == 201

    response = api_client.get(
        _session_collection_url(
            user["id"],
            french_profile["id"],
        )
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["id"] == french_session.json()["id"]


# ---------------------------------------------------------------------------
# Cross-profile ownership
# ---------------------------------------------------------------------------


def test_session_cannot_be_read_through_another_profile(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)

    french_profile = _create_profile(
        api_client,
        user["id"],
        language_code="fr",
        variant_code="fr-CA",
    )

    english_profile = _create_profile(
        api_client,
        user["id"],
        language_code="en",
        variant_code="en-CA",
        cefr_level="C1",
    )

    create_response = api_client.post(
        _session_collection_url(
            user["id"],
            french_profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "professional",
        },
    )

    assert create_response.status_code == 201

    practice_session_id = create_response.json()["id"]

    response = api_client.get(
        _session_detail_url(
            user["id"],
            english_profile["id"],
            practice_session_id,
        )
    )

    assert response.status_code == 404


def test_session_cannot_be_read_through_another_user(
    api_client: TestClient,
) -> None:
    owner = _create_user(
        api_client,
        "Owner",
    )

    other = _create_user(
        api_client,
        "Other",
    )

    profile = _create_profile(
        api_client,
        owner["id"],
    )

    create_response = api_client.post(
        _session_collection_url(
            owner["id"],
            profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "professional",
        },
    )

    assert create_response.status_code == 201

    response = api_client.get(
        _session_detail_url(
            other["id"],
            profile["id"],
            create_response.json()["id"],
        )
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Historical CEFR snapshot
# ---------------------------------------------------------------------------


def test_historical_session_keeps_original_cefr_snapshot(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)

    profile = _create_profile(
        api_client,
        user["id"],
        cefr_level="B2",
    )

    create_response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "professional",
        },
    )

    assert create_response.status_code == 201

    created = create_response.json()

    assert created["profile_cefr"] == "B2"
    assert created["target_cefr"] is None
    assert created["effective_cefr"] == "B2"

    update_response = api_client.patch(
        (
            f"/users/{user['id']}"
            f"/language-profiles/{profile['id']}"
        ),
        json={
            "cefr_level": "C1",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["cefr_level"] == "C1"

    response = api_client.get(
        _session_detail_url(
            user["id"],
            profile["id"],
            created["id"],
        )
    )

    assert response.status_code == 200

    body = response.json()

    assert body["profile_cefr"] == "B2"
    assert body["target_cefr"] is None
    assert body["effective_cefr"] == "B2"

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_complete_active_practice_session(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    create_response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "professional",
        },
    )

    assert create_response.status_code == 201

    created = create_response.json()

    assert created["status"] == "active"
    assert created["ended_at"] is None

    response = api_client.post(
        (
            f"{_session_detail_url(
                user['id'],
                profile['id'],
                created['id'],
            )}/complete"
        )
    )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == created["id"]
    assert body["status"] == "completed"
    assert body["ended_at"] is not None

    get_response = api_client.get(
        _session_detail_url(
            user["id"],
            profile["id"],
            created["id"],
        )
    )

    assert get_response.status_code == 200

    persisted = get_response.json()

    assert persisted["status"] == "completed"
    assert persisted["ended_at"] is not None

def test_abandon_active_practice_session(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    create_response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "conversation",
            "register": "everyday",
        },
    )

    assert create_response.status_code == 201

    created = create_response.json()

    response = api_client.post(
        (
            f"{_session_detail_url(
                user['id'],
                profile['id'],
                created['id'],
            )}/abandon"
        )
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "abandoned"
    assert body["ended_at"] is not None


def test_completed_session_cannot_be_abandoned(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    create_response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "professional",
        },
    )

    assert create_response.status_code == 201

    practice_session_id = create_response.json()["id"]

    detail_url = _session_detail_url(
        user["id"],
        profile["id"],
        practice_session_id,
    )

    complete_response = api_client.post(
        f"{detail_url}/complete"
    )

    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"

    abandon_response = api_client.post(
        f"{detail_url}/abandon"
    )

    assert abandon_response.status_code == 409


def test_abandoned_session_cannot_be_completed(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    create_response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "conversation",
            "register": "everyday",
        },
    )

    assert create_response.status_code == 201

    practice_session_id = create_response.json()["id"]

    detail_url = _session_detail_url(
        user["id"],
        profile["id"],
        practice_session_id,
    )

    abandon_response = api_client.post(
        f"{detail_url}/abandon"
    )

    assert abandon_response.status_code == 200
    assert abandon_response.json()["status"] == "abandoned"

    complete_response = api_client.post(
        f"{detail_url}/complete"
    )

    assert complete_response.status_code == 409


def test_completed_session_cannot_be_completed_again(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = _create_profile(
        api_client,
        user["id"],
    )

    create_response = api_client.post(
        _session_collection_url(
            user["id"],
            profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "professional",
        },
    )

    practice_session_id = create_response.json()["id"]

    detail_url = _session_detail_url(
        user["id"],
        profile["id"],
        practice_session_id,
    )

    first_response = api_client.post(
        f"{detail_url}/complete"
    )

    assert first_response.status_code == 200

    second_response = api_client.post(
        f"{detail_url}/complete"
    )

    assert second_response.status_code == 409


def test_other_user_cannot_complete_practice_session(
    api_client: TestClient,
) -> None:
    owner = _create_user(
        api_client,
        "Owner",
    )

    other = _create_user(
        api_client,
        "Other",
    )

    profile = _create_profile(
        api_client,
        owner["id"],
    )

    create_response = api_client.post(
        _session_collection_url(
            owner["id"],
            profile["id"],
        ),
        json={
            "training_mode": "professional",
            "register": "professional",
        },
    )

    assert create_response.status_code == 201

    practice_session_id = create_response.json()["id"]

    response = api_client.post(
        (
            f"/users/{other['id']}"
            f"/language-profiles/{profile['id']}"
            f"/sessions/{practice_session_id}/complete"
        )
    )

    assert response.status_code == 404

