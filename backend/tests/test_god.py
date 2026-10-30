import pytest
from fastapi.testclient import TestClient

from app import special_users
from app.main import app
from app.services import limits


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def test_god_requires_authentication(client):
    assert client.get("/god/settings").status_code == 401


def test_god_rejects_non_god_user(client, admin_headers):
    assert client.get("/god/settings", headers=admin_headers).status_code == 403


def test_god_accepts_the_god_user(client, god_headers):
    assert client.get("/god/me", headers=god_headers).status_code == 200


def test_god_settings_list_matches_current_values(client, god_headers):
    response = client.get("/god/settings", headers=god_headers)

    assert response.status_code == 200
    settings = {item["key"]: item for item in response.json()["settings"]}
    assert settings["max_grid_size"]["value"] == 20
    assert settings["gemini_timeout_seconds"]["value"] == 45
    assert settings["max_clue_length"]["value"] == 500
    assert settings["parser_timeout_seconds"]["value"] == 30


def test_god_can_change_a_limit_and_reset_it(client, god_headers):
    changed = client.put(
        "/god/settings",
        headers=god_headers,
        json={"values": {"max_grid_size": 25, "gemini_timeout_seconds": 60}},
    )
    assert changed.status_code == 200
    assert limits.get_limits().max_grid_size == 25
    assert limits.get_limits().gemini_timeout_seconds == 60

    reset = client.post("/god/settings/reset", headers=god_headers)
    assert reset.status_code == 200
    assert limits.get_limits().max_grid_size == 20


def test_god_rejects_invalid_limit_values(client, god_headers):
    response = client.put(
        "/god/settings",
        headers=god_headers,
        json={"values": {"max_grid_size": 999}},
    )

    assert response.status_code == 400
    assert limits.get_limits().max_grid_size == 20


def test_god_rejects_unknown_settings(client, god_headers):
    response = client.put(
        "/god/settings",
        headers=god_headers,
        json={"values": {"unlimited_everything": True}},
    )

    assert response.status_code == 400


def test_god_can_add_and_remove_a_user(client, god_headers):
    added = client.post(
        "/god/users",
        headers=god_headers,
        json={"email": "Helper@Example.com", "role": "admin"},
    )
    assert added.status_code == 201
    assert added.json() == {"email": "helper@example.com", "role": "admin"}

    removed = client.delete("/god/users/helper@example.com", headers=god_headers)
    assert removed.status_code == 200


def test_god_cannot_remove_the_primary_god(client, god_headers):
    response = client.delete("/god/users/tal.vazanas@gmail.com", headers=god_headers)

    assert response.status_code == 400


def test_god_cannot_remove_an_unknown_user(client, god_headers):
    response = client.delete("/god/users/nobody@example.com", headers=god_headers)

    assert response.status_code == 404


def test_god_rejects_invalid_role(client, god_headers):
    response = client.post(
        "/god/users",
        headers=god_headers,
        json={"email": "someone@example.com", "role": "player"},
    )

    assert response.status_code == 422


def test_god_status_does_not_leak_secrets(client, god_headers, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-gemini-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100")

    response = client.get("/god/status", headers=god_headers)
    body = response.text

    assert response.status_code == 200
    assert "secret-gemini-key" not in body
    assert "secret-bot-token" not in body
    snapshot = response.json()
    assert snapshot["geminiConfigured"] is True
    assert snapshot["telegramConfigured"] is True


def test_restore_overrides_applies_saved_values_and_skips_bad_entries():
    limits.restore_overrides(
        {
            "max_grid_size": 22,
            "gemini_timeout_seconds": 90,
            "unknown_setting": 1,
            "max_clues": 0,
        }
    )

    current = limits.get_limits()
    assert current.max_grid_size == 22
    assert current.gemini_timeout_seconds == 90
    assert current.max_clues == 500


def test_restore_special_users_keeps_the_primary_god():
    special_users.restore_special_users(
        {
            "Helper@Example.com": "admin",
            "stranger@example.com": "owner",
            "tal.vazanas@gmail.com": "admin",
        }
    )

    assert special_users.is_god("tal.vazanas@gmail.com")
    assert special_users.website_role_for_email("helper@example.com") == "admin"
    assert special_users.website_role_for_email("stranger@example.com") is None

def test_god_lists_all_signed_in_users(client, god_headers):
    from app.services import profiles
    profiles.record_seen("player1@example.com")
    profiles.set_nickname("player1@example.com", "Dana")
    profiles.record_seen("player2@example.com")

    response = client.get("/god/users/all", headers=god_headers)

    assert response.status_code == 200
    users = {u["email"]: u for u in response.json()["users"]}
    assert users["player1@example.com"]["nickname"] == "Dana"
    assert users["player1@example.com"]["role"] is None
    assert users["player2@example.com"]["nickname"] is None
