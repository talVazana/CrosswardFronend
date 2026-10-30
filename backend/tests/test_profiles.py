from fastapi.testclient import TestClient

from app.main import app
from app.services import profiles


def client():
    return TestClient(app, base_url="https://testserver")


def test_profile_requires_authentication():
    with client() as c:
        assert c.get("/me/profile").status_code == 401
        assert c.put("/me/profile", json={"nickname": "Dana"}).status_code == 401


def test_set_and_get_nickname(player_headers):
    with client() as c:
        put = c.put("/me/profile", json={"nickname": "Dana"}, headers=player_headers)
        assert put.status_code == 200, put.text
        assert put.json()["nickname"] == "Dana"

        got = c.get("/me/profile", headers=player_headers)
        assert got.status_code == 200
        assert got.json()["nickname"] == "Dana"
        assert got.json()["email"] == "player@example.com"


def test_nickname_must_be_within_length_bounds(player_headers):
    with client() as c:
        too_short = c.put("/me/profile", json={"nickname": "A"}, headers=player_headers)
        assert too_short.status_code == 422

        too_long = c.put(
            "/me/profile", json={"nickname": "x" * 21}, headers=player_headers
        )
        assert too_long.status_code == 422


def test_nickname_is_unique_per_email(player_headers, admin_headers):
    with client() as c:
        c.put("/me/profile", json={"nickname": "Dana"}, headers=player_headers)
        c.put("/me/profile", json={"nickname": "Shachar"}, headers=admin_headers)

        assert c.get("/me/profile", headers=player_headers).json()["nickname"] == "Dana"
        assert (
            c.get("/me/profile", headers=admin_headers).json()["nickname"] == "Shachar"
        )


def test_restore_profiles_skips_invalid_nicknames():
    profiles.reset_profiles()
    profiles.restore_profiles(
        {"dana@example.com": "Dana", "bad@example.com": "X", "empty@example.com": ""}
    )

    assert profiles.get_nickname("dana@example.com") == "Dana"
    assert profiles.get_nickname("bad@example.com") is None
    assert profiles.get_nickname("empty@example.com") is None
