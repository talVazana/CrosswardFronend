import pytest
from fastapi.testclient import TestClient

from app.api.routes import admin as admin_module
from app.api.routes import rooms as rooms_module
from app.main import app
from app.models.answers import OfficialAnswers
from app.models.room import Player
from app.repositories.in_memory import InMemoryAnswerRepository, InMemoryPlayerRepository

ROOM_ID = "room-1"
ADMIN_ID = "admin-1"
PLAYER_ID = "player-1"
TOKEN_ADMIN = "token-room-1-admin-1"
TOKEN_PLAYER = "token-room-1-player-1"

PUZZLE_ID = "puz1"
CLUE_ID = "A1"
URL = f"/admin/puzzles/{PUZZLE_ID}/clues/{CLUE_ID}/answer"


def make_player(player_id: str, role: str) -> Player:
    return Player(
        roomId=ROOM_ID,
        playerId=player_id,
        displayName=player_id,
        color="#AABBCC",
        role=role,
    )


@pytest.fixture
def clients():
    player_repository = InMemoryPlayerRepository()
    player_repository.add(make_player(ADMIN_ID, "admin"))
    player_repository.add(make_player(PLAYER_ID, "player"))

    answer_repository = InMemoryAnswerRepository()

    rooms_module.player_repository = player_repository
    rooms_module._sessions.clear()
    rooms_module._sessions[TOKEN_ADMIN] = (ROOM_ID, ADMIN_ID)
    rooms_module._sessions[TOKEN_PLAYER] = (ROOM_ID, PLAYER_ID)
    admin_module.answer_repository = answer_repository

    with TestClient(app, base_url="https://testserver") as admin_client, TestClient(
        app, base_url="https://testserver"
    ) as player_client:
        admin_client.cookies.set("Session-Token", TOKEN_ADMIN)
        player_client.cookies.set("Session-Token", TOKEN_PLAYER)
        yield admin_client, player_client, answer_repository

    rooms_module._sessions.clear()
    admin_module.answer_repository = InMemoryAnswerRepository()


def test_admin_put_returns_200_ok(clients):
    admin_client, _, _ = clients
    response = admin_client.put(URL, json={"answer": "  apple  "})
    assert response.status_code == 200


def test_admin_put_saves_normalized_answer(clients):
    admin_client, _, answer_repository = clients
    response = admin_client.put(URL, json={"answer": "  apple  "})
    assert response.status_code == 200

    stored = answer_repository.get(PUZZLE_ID)
    assert stored is not None
    assert stored.answers[CLUE_ID] == "APPLE"


def test_player_put_returns_403_and_does_not_alter_repository(clients):
    _, player_client, answer_repository = clients
    answer_repository.save(
        OfficialAnswers(puzzleId=PUZZLE_ID, answers={CLUE_ID: "APPLE"})
    )

    response = player_client.put(URL, json={"answer": "  banana  "})
    assert response.status_code == 403

    stored = answer_repository.get(PUZZLE_ID)
    assert stored is not None
    assert stored.answers[CLUE_ID] == "APPLE"


def test_empty_string_payload_overwrites_official_answer(clients):
    admin_client, _, answer_repository = clients
    assert admin_client.put(URL, json={"answer": "apple"}).status_code == 200
    assert answer_repository.get(PUZZLE_ID).answers[CLUE_ID] == "APPLE"

    response = admin_client.put(URL, json={"answer": ""})
    assert response.status_code == 200

    stored = answer_repository.get(PUZZLE_ID)
    assert stored is not None
    assert stored.answers[CLUE_ID] == ""


def test_missing_token_returns_401_or_403_and_does_not_alter_repository(clients):
    _, _, answer_repository = clients
    answer_repository.save(
        OfficialAnswers(puzzleId=PUZZLE_ID, answers={CLUE_ID: "APPLE"})
    )

    with TestClient(app, base_url="https://testserver") as anonymous_client:
        response = anonymous_client.put(URL, json={"answer": "banana"})

    assert response.status_code in (401, 403)
    stored = answer_repository.get(PUZZLE_ID)
    assert stored is not None
    assert stored.answers[CLUE_ID] == "APPLE"
