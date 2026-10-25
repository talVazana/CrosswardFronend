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

ACTIVE_ROOM = "room-active"
LOBBY_ROOM = "room-lobby"
PAUSED_ROOM = "room-paused"
FINISHED_ROOM = "room-finished"
ADMIN_ID = "admin-1"
PLAYER_ID = "player-1"
ADMIN_TOKEN = "token-admin"
PLAYER_TOKEN = "token-player"


def make_puzzle(puzzle_id: str) -> Puzzle:
    return Puzzle(
        puzzleId=puzzle_id,
        title=f"Puzzle {puzzle_id}",
        width=2,
        height=2,
        cells=[
            Cell(row=0, col=0, type="white", number=1, startsAcross=True, startsDown=False),
            Cell(row=0, col=1, type="white", number=None, startsAcross=False, startsDown=False),
            Cell(row=1, col=0, type="white", number=2, startsAcross=False, startsDown=True),
            Cell(row=1, col=1, type="black", number=None, startsAcross=False, startsDown=False),
        ],
        clues=[
            Clue(
                clueId="A1",
                number=1,
                direction="across",
                text="Across clue",
                answerLength=2,
            ),
            Clue(
                clueId="D2",
                number=2,
                direction="down",
                text="Down clue",
                answerLength=2,
            ),
        ],
    )


def make_room(room_id: str, title: str, status: RoomStatus) -> Room:
    return Room(
        roomId=room_id,
        title=title,
        status=status,
        puzzleSnapshot=make_puzzle(f"puzzle-{room_id}"),
        creatorId=ADMIN_ID,
    )


@pytest.fixture
def env(monkeypatch):
    room_repository = InMemoryRoomRepository()
    room_repository.create(make_room(ACTIVE_ROOM, "Alpha", RoomStatus.active))
    room_repository.create(make_room(LOBBY_ROOM, "Beta", RoomStatus.lobby))
    room_repository.create(make_room(PAUSED_ROOM, "Delta", RoomStatus.paused))
    room_repository.create(make_room(FINISHED_ROOM, "Gamma", RoomStatus.finished))

    player_repository = InMemoryPlayerRepository()
    player_repository.add(
        Player(
            roomId=ACTIVE_ROOM,
            playerId=ADMIN_ID,
            displayName="Admin",
            color="#AABBCC",
            role="admin",
        )
    )
    player_repository.add(
        Player(
            roomId=ACTIVE_ROOM,
            playerId=PLAYER_ID,
            displayName="Player",
            color="#CCBBAA",
            role="player",
        )
    )

    sessions = {
        ADMIN_TOKEN: (ACTIVE_ROOM, ADMIN_ID),
        PLAYER_TOKEN: (ACTIVE_ROOM, PLAYER_ID),
    }

    monkeypatch.setattr(rooms_module, "room_repository", room_repository)
    monkeypatch.setattr(rooms_module, "player_repository", player_repository)
    monkeypatch.setattr(rooms_module, "_sessions", sessions)

    return SimpleNamespace(
        room_repository=room_repository,
        player_repository=player_repository,
        sessions=sessions,
    )


@pytest.fixture
def client(env):
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def test_public_room_gallery_lists_all_rooms_with_statuses(client):
    response = client.get("/rooms")

    assert response.status_code == 200, response.text
    rooms = response.json()
    assert [room["roomId"] for room in rooms] == [
        ACTIVE_ROOM,
        LOBBY_ROOM,
        PAUSED_ROOM,
        FINISHED_ROOM,
    ]
    assert [room["status"] for room in rooms] == [
        "active",
        "lobby",
        "paused",
        "finished",
    ]


def test_public_room_gallery_returns_summary_fields_and_player_counts(client):
    response = client.get("/rooms")

    assert response.status_code == 200, response.text
    by_id = {room["roomId"]: room for room in response.json()}
    active = by_id[ACTIVE_ROOM]
    assert active["title"] == "Alpha"
    assert active["playerCount"] == 1
    assert active["width"] == 2
    assert active["height"] == 2
    assert active["clueCount"] == 2
    assert by_id[LOBBY_ROOM]["playerCount"] == 0


def test_admin_room_gallery_requires_an_admin_session(client, env):
    response = client.get("/admin/rooms")
    assert response.status_code == 401

    client.cookies.set(rooms_module.SESSION_COOKIE_NAME, PLAYER_TOKEN)
    response = client.get("/admin/rooms")
    assert response.status_code == 403


def test_admin_session_cookie_is_separate_from_player_session(client, env):
    client.cookies.set(rooms_module.SESSION_COOKIE_NAME, PLAYER_TOKEN)

    response = client.post("/admin/session", json={"token": ADMIN_TOKEN})

    assert response.status_code == 200, response.text
    assert response.json()["displayName"] == "Admin"
    assert client.cookies.get("Admin-Session-Token") == ADMIN_TOKEN
    assert client.cookies.get(rooms_module.SESSION_COOKIE_NAME) == PLAYER_TOKEN


def test_admin_session_cookie_grants_access_to_admin_gallery(client, env):
    client.cookies.set(rooms_module.SESSION_COOKIE_NAME, PLAYER_TOKEN)
    login = client.post("/admin/session", json={"token": ADMIN_TOKEN})
    assert login.status_code == 200, login.text

    response = client.get("/admin/rooms")

    assert response.status_code == 200, response.text
    assert len(response.json()) == 4


def test_admin_session_rejects_invalid_and_player_tokens(client, env):
    invalid = client.post("/admin/session", json={"token": "not-a-session"})
    assert invalid.status_code == 401

    player = client.post("/admin/session", json={"token": PLAYER_TOKEN})
    assert player.status_code == 403
    assert client.cookies.get("Admin-Session-Token") is None


def test_admin_password_login_grants_access_to_admin_gallery(client, env):
    response = client.post("/admin/session", json={"password": "1234"})

    assert response.status_code == 200, response.text
    assert response.json()["displayName"] == "Admin"
    assert client.cookies.get("Admin-Session-Token") is not None

    gallery = client.get("/admin/rooms")
    assert gallery.status_code == 200, gallery.text
    assert len(gallery.json()) == 4


def test_admin_password_login_rejects_wrong_password(client, env):
    response = client.post("/admin/session", json={"password": "9999"})

    assert response.status_code == 401
    assert client.cookies.get("Admin-Session-Token") is None
