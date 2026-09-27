import uuid

from fastapi.testclient import TestClient


def _create_user(client: TestClient, name: str = "Ricardo") -> dict:
    response = client.post("/users", json={"display_name": name})
    assert response.status_code == 201
    return response.json()


def _profile_payload(
    *,
    language_code: str = "fr",
    variant_code: str = "fr-CA",
    cefr_level: str = "B2",
    production: str = "professional",
    comprehension: list[str] | None = None,
) -> dict:
    return {
        "language_code": language_code,
        "variant_code": variant_code,
        "cefr_level": cefr_level,
        "default_production_register_code": production,
        "comprehension_register_codes": (
            comprehension
            if comprehension is not None
            else ["professional", "everyday", "colloquial"]
        ),
    }


def test_create_get_and_list_users(api_client: TestClient) -> None:
    ricardo = _create_user(api_client, "  Ricardo  ")
    _create_user(api_client, "Alice")

    assert ricardo["display_name"] == "Ricardo"

    response = api_client.get(f"/users/{ricardo['id']}")
    assert response.status_code == 200
    assert response.json()["display_name"] == "Ricardo"

    response = api_client.get("/users")
    assert response.status_code == 200
    assert [user["display_name"] for user in response.json()] == [
        "Alice",
        "Ricardo",
    ]


def test_create_user_rejects_blank_name(api_client: TestClient) -> None:
    response = api_client.post("/users", json={"display_name": "   "})

    assert response.status_code == 422


def test_get_unknown_user_returns_404(api_client: TestClient) -> None:
    response = api_client.get(f"/users/{uuid.uuid4()}")

    assert response.status_code == 404


def test_list_languages_and_variants(api_client: TestClient) -> None:
    response = api_client.get("/languages")
    assert response.status_code == 200
    assert [item["code"] for item in response.json()] == ["en", "fr"]

    response = api_client.get("/languages/fr/variants")
    assert response.status_code == 200
    assert [item["code"] for item in response.json()] == ["fr-CA", "fr-FR"]
    assert response.json()[0]["regional_focus"] == "Québec"


def test_unknown_language_variants_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/languages/xx/variants")

    assert response.status_code == 404


def test_list_communication_registers(api_client: TestClient) -> None:
    response = api_client.get("/communication-registers")

    assert response.status_code == 200
    registers = {item["code"]: item for item in response.json()}
    assert set(registers) == {
        "professional",
        "formal_executive",
        "everyday",
        "conversational",
        "colloquial",
    }
    assert registers["colloquial"]["production_allowed"] is True
    assert registers["colloquial"]["comprehension_allowed"] is True


def test_create_get_and_list_language_profile(api_client: TestClient) -> None:
    user = _create_user(api_client)

    response = api_client.post(
        f"/users/{user['id']}/language-profiles",
        json=_profile_payload(),
    )
    assert response.status_code == 201
    profile = response.json()

    assert profile["language"]["code"] == "fr"
    assert profile["variant"]["code"] == "fr-CA"
    assert profile["variant"]["regional_focus"] == "Québec"
    assert profile["cefr_level"] == "B2"
    assert profile["default_production_register"]["code"] == "professional"
    assert {
        register["code"] for register in profile["comprehension_registers"]
    } == {"professional", "everyday", "colloquial"}

    response = api_client.get(
        f"/users/{user['id']}/language-profiles/{profile['id']}"
    )
    assert response.status_code == 200
    assert response.json()["id"] == profile["id"]

    response = api_client.get(f"/users/{user['id']}/language-profiles")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [profile["id"]]


def test_language_profile_invalid_cefr_returns_422(api_client: TestClient) -> None:
    user = _create_user(api_client)
    payload = _profile_payload()
    payload["cefr_level"] = "B3"

    response = api_client.post(
        f"/users/{user['id']}/language-profiles",
        json=payload,
    )

    assert response.status_code == 422


def test_language_profile_unknown_variant_returns_422(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)

    response = api_client.post(
        f"/users/{user['id']}/language-profiles",
        json=_profile_payload(variant_code="fr-BE"),
    )

    assert response.status_code == 422
    assert "fr-BE" in response.json()["detail"]


def test_language_variant_mismatch_returns_422(api_client: TestClient) -> None:
    user = _create_user(api_client)

    response = api_client.post(
        f"/users/{user['id']}/language-profiles",
        json=_profile_payload(language_code="en", variant_code="fr-CA"),
    )

    assert response.status_code == 422
    assert "does not belong" in response.json()["detail"]


def test_duplicate_profile_returns_409(api_client: TestClient) -> None:
    user = _create_user(api_client)
    url = f"/users/{user['id']}/language-profiles"

    assert api_client.post(url, json=_profile_payload()).status_code == 201
    response = api_client.post(url, json=_profile_payload())

    assert response.status_code == 409


def test_user_can_have_multiple_language_profiles(api_client: TestClient) -> None:
    user = _create_user(api_client)
    url = f"/users/{user['id']}/language-profiles"

    assert api_client.post(url, json=_profile_payload()).status_code == 201
    assert api_client.post(
        url,
        json=_profile_payload(variant_code="fr-FR", cefr_level="B1"),
    ).status_code == 201
    assert api_client.post(
        url,
        json=_profile_payload(
            language_code="en",
            variant_code="en-CA",
            cefr_level="C1",
        ),
    ).status_code == 201

    response = api_client.get(url)
    assert response.status_code == 200
    assert {item["variant"]["code"] for item in response.json()} == {
        "fr-CA",
        "fr-FR",
        "en-CA",
    }


def test_profile_ownership_is_enforced_by_nested_route(
    api_client: TestClient,
) -> None:
    owner = _create_user(api_client, "Owner")
    other = _create_user(api_client, "Other")
    response = api_client.post(
        f"/users/{owner['id']}/language-profiles",
        json=_profile_payload(),
    )
    profile = response.json()

    response = api_client.get(
        f"/users/{other['id']}/language-profiles/{profile['id']}"
    )

    assert response.status_code == 404


def test_update_language_profile(api_client: TestClient) -> None:
    user = _create_user(api_client)
    response = api_client.post(
        f"/users/{user['id']}/language-profiles",
        json=_profile_payload(),
    )
    profile = response.json()

    response = api_client.patch(
        f"/users/{user['id']}/language-profiles/{profile['id']}",
        json={
            "language_code": "fr",
            "variant_code": "fr-FR",
            "cefr_level": "C1",
            "default_production_register_code": "colloquial",
            "comprehension_register_codes": [
                "colloquial",
                "conversational",
            ],
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["variant"]["code"] == "fr-FR"
    assert updated["cefr_level"] == "C1"
    assert updated["default_production_register"]["code"] == "colloquial"
    assert {
        item["code"] for item in updated["comprehension_registers"]
    } == {"colloquial", "conversational"}


def test_update_profile_can_clear_comprehension_registers(
    api_client: TestClient,
) -> None:
    user = _create_user(api_client)
    profile = api_client.post(
        f"/users/{user['id']}/language-profiles",
        json=_profile_payload(),
    ).json()

    response = api_client.patch(
        f"/users/{user['id']}/language-profiles/{profile['id']}",
        json={"comprehension_register_codes": []},
    )

    assert response.status_code == 200
    assert response.json()["comprehension_registers"] == []


def test_empty_profile_patch_returns_422(api_client: TestClient) -> None:
    user = _create_user(api_client)
    profile = api_client.post(
        f"/users/{user['id']}/language-profiles",
        json=_profile_payload(),
    ).json()

    response = api_client.patch(
        f"/users/{user['id']}/language-profiles/{profile['id']}",
        json={},
    )

    assert response.status_code == 422


def test_unknown_user_profile_route_returns_404(api_client: TestClient) -> None:
    response = api_client.get(
        f"/users/{uuid.uuid4()}/language-profiles"
    )

    assert response.status_code == 404
