from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.routes import rooms as rooms_module
from app.main import app
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Player, Room, RoomStatus
from app.repositories.in_memory import (
    InMemoryPlayerRepository,
    InMemoryRoomRepository,
)

ROOM_ID = "room-1"
MISSING_ROOM_ID = "room-does-not-exist"
PUZZLE_ID = "puzzle-1"
ADMIN_ID = "admin-1"
PLAYER_ID = "player-1"
ADMIN_TOKEN = "token-room-1-admin"
PLAYER_TOKEN = "token-room-1-player"
COLOR_ADMIN = "#AABBCC"
COLOR_PLAYER = "#CCBBAA"


def make_puzzle():
    return Puzzle(
        puzzleId=PUZZLE_ID,
        title="Test Puzzle",
        width=1,
        height=1,
        cells=[
            Cell(
                row=0,
                col=0,
                type="white",
                number=1,
                startsAcross=True,
                startsDown=False,
            )
        ],
        clues=[
            Clue(
                clueId="A1",
                number=1,
                direction="across",
                text="Fruit clue",
                answerLength=5,
            )
        ],
    )


def make_room(status):
    return Room(
        roomId=ROOM_ID,
        title="Test Room",
        status=status,
        puzzleSnapshot=make_puzzle(),
        creatorId=ADMIN_ID,
    )


def make_player(player_id, role, color):
    return Player(
        roomId=ROOM_ID,
        playerId=player_id,
        displayName=player_id,
        color=color,
        role=role,
    )


@pytest.fixture
def env(monkeypatch):
    def build(status=RoomStatus.lobby, include_room=True):
        room_repository = InMemoryRoomRepository()
        if include_room:
            room_repository.create(make_room(status))

        player_repository = InMemoryPlayerRepository()
        player_repository.add(make_player(ADMIN_ID, "admin", COLOR_ADMIN))
        player_repository.add(make_player(PLAYER_ID, "player", COLOR_PLAYER))

        sessions = {
            ADMIN_TOKEN: (ROOM_ID, ADMIN_ID),
            PLAYER_TOKEN: (ROOM_ID, PLAYER_ID),
        }

        monkeypatch.setattr(rooms_module, "room_repository", room_repository)
        monkeypatch.setattr(rooms_module, "player_repository", player_repository)
        monkeypatch.setattr(rooms_module, "_sessions", sessions)

        return SimpleNamespace(room_repository=room_repository)

    return build


@pytest.fixture
def client(env):
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def login_as(client, token):
    client.cookies.set("Session-Token", token)


def test_scenario_admin_starts_lobby_room_returns_200_and_persists_active(client, env):
    api_env = env(RoomStatus.lobby)
    login_as(client, ADMIN_TOKEN)

    response = client.post(f"/admin/rooms/{ROOM_ID}/start")

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert api_env.room_repository.get(ROOM_ID).status == RoomStatus.active


def test_scenario_start_finished_room_returns_400_and_state_unchanged(client, env):
    api_env = env(RoomStatus.finished)
    login_as(client, ADMIN_TOKEN)

    response = client.post(f"/admin/rooms/{ROOM_ID}/start")

    assert response.status_code == 400
    assert api_env.room_repository.get(ROOM_ID).status == RoomStatus.finished


def test_scenario_player_pauses_active_room_returns_403(client, env):
    api_env = env(RoomStatus.active)
    login_as(client, PLAYER_TOKEN)

    response = client.post(f"/admin/rooms/{ROOM_ID}/pause")

    assert response.status_code == 403
    assert api_env.room_repository.get(ROOM_ID).status == RoomStatus.active


def test_edge_unknown_room_returns_404(client, env):
    env(RoomStatus.lobby)
    login_as(client, ADMIN_TOKEN)

    response = client.post(f"/admin/rooms/{MISSING_ROOM_ID}/start")

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("initial", "action", "expected"),
    [
        (RoomStatus.lobby, "start", RoomStatus.active),
        (RoomStatus.active, "pause", RoomStatus.paused),
        (RoomStatus.paused, "resume", RoomStatus.active),
        (RoomStatus.active, "finish", RoomStatus.finished),
        (RoomStatus.paused, "finish", RoomStatus.finished),
        (RoomStatus.finished, "close", RoomStatus.closed),
    ],
)
def test_acceptance_all_valid_transitions_succeed_and_persist(
    client, env, initial, action, expected
):
    api_env = env(initial)
    login_as(client, ADMIN_TOKEN)

    response = client.post(f"/admin/rooms/{ROOM_ID}/{action}")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == expected.value
    assert api_env.room_repository.get(ROOM_ID).status == expected


@pytest.mark.parametrize(
    ("initial", "action"),
    [
        (RoomStatus.finished, "start"),
        (RoomStatus.closed, "start"),
        (RoomStatus.paused, "start"),
        (RoomStatus.lobby, "pause"),
        (RoomStatus.lobby, "resume"),
        (RoomStatus.lobby, "finish"),
        (RoomStatus.closed, "close"),
    ],
)
def test_acceptance_invalid_transitions_return_400_and_do_not_alter_db(
    client, env, initial, action
):
    api_env = env(initial)
    login_as(client, ADMIN_TOKEN)

    response = client.post(f"/admin/rooms/{ROOM_ID}/{action}")

    assert response.status_code == 400, response.text
    assert api_env.room_repository.get(ROOM_ID).status == initial


@pytest.mark.parametrize("action", ["start", "pause", "resume", "finish", "close"])
def test_acceptance_non_admin_blocked_on_every_endpoint(client, env, action):
    env(RoomStatus.active)
    login_as(client, PLAYER_TOKEN)

    response = client.post(f"/admin/rooms/{ROOM_ID}/{action}")

    assert response.status_code == 403, response.text
