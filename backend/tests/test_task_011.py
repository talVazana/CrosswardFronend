import pytest
from fastapi.testclient import TestClient

from app.api.routes import rooms as rooms_module
from app.main import app
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import ASSIGNED_PLAYER_COLORS, Room, RoomStatus
from app.repositories.in_memory import InMemoryPlayerRepository, InMemoryRoomRepository
from app.services.room_service import RoomService

ROOM_ID = "test-room"


def make_puzzle() -> Puzzle:
    return Puzzle(
        puzzleId="puzzle_test",
        title="Secret Puzzle",
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
                clueId="clue1",
                number=1,
                direction="across",
                text="Secret clue",
                answerLength=1,
            )
        ],
    )


def make_room() -> Room:
    return Room(
        roomId=ROOM_ID,
        title="Test Room",
        status=RoomStatus.lobby,
        puzzleSnapshot=make_puzzle(),
        creatorId="creator1",
    )


@pytest.fixture
def client():
    room_repository = InMemoryRoomRepository()
    player_repository = InMemoryPlayerRepository()
    room_repository.create(make_room())

    rooms_module.room_repository = room_repository
    rooms_module.player_repository = player_repository
    rooms_module.room_service = RoomService(room_repository, player_repository)
    rooms_module._sessions.clear()

    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client

    rooms_module._sessions.clear()


def join(client, display_name="Dana", color="#FF0000"):
    return client.post(
        f"/rooms/{ROOM_ID}/join",
        json={"displayName": display_name, "color": color},
    )


def state(client):
    return client.get(f"/rooms/{ROOM_ID}/state")


def test_join_valid_returns_200_and_sets_httponly_session_cookie(client):
    response = join(client)
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "Session-Token=" in set_cookie
    assert "httponly" in set_cookie.lower()


def test_join_valid_returns_created_player(client):
    response = join(client)
    assert response.status_code == 200
    body = response.json()
    assert "playerId" in body
    assert body["playerId"]

    players = state(client).json()["players"]
    assert any(player["playerId"] == body["playerId"] for player in players)


def test_rejoin_with_same_session_cookie_and_new_name_creates_second_player(client):
    first = join(client)
    assert first.status_code == 200
    first_player_id = first.json()["playerId"]
    assert len(state(client).json()["players"]) == 1

    second = join(client, display_name="Dana Again", color="#00FF00")
    assert second.status_code == 200
    assert second.json()["playerId"] != first_player_id

    players = state(client).json()["players"]
    assert len(players) == 2
    assert sorted(player["displayName"] for player in players) == ["Dana", "Dana Again"]


def test_state_returns_title_status_and_players_without_secrets(client):
    joined = join(client)
    assert joined.status_code == 200
    session_token = joined.cookies.get("Session-Token")
    assert session_token

    response = state(client)
    assert response.status_code == 200
    body = response.json()

    assert body["title"] == "Test Room"
    assert body["status"] == "lobby"

    players = body.get("players", body.get("participants"))
    assert isinstance(players, list) and len(players) == 1
    assert players[0]["displayName"] == "Dana"
    assert players[0]["color"] == ASSIGNED_PLAYER_COLORS[0]

    lowered_keys = {key.lower() for key in body}
    for forbidden in ("puzzlesnapshot", "puzzle_snapshot", "session", "session-token", "sessiontoken"):
        assert forbidden not in lowered_keys
    for player in players:
        player_keys = {key.lower() for key in player}
        for forbidden in ("draft", "drafts", "session", "session-token", "sessiontoken"):
            assert forbidden not in player_keys
    assert session_token not in response.text


def test_client_supplied_color_is_ignored_and_system_color_is_used(client):
    response = join(client, color="blue")

    assert response.status_code == 200
    player = state(client).json()["players"][0]
    assert player["color"] == ASSIGNED_PLAYER_COLORS[0]


def test_each_player_gets_a_distinct_system_assigned_color(client):
    first = join(client, display_name="Dana")
    assert first.status_code == 200
    client.cookies.clear()

    second = join(client, display_name="Amir")
    assert second.status_code == 200

    players = state(client).json()["players"]
    colors = sorted(player["color"] for player in players)
    assert colors == sorted(ASSIGNED_PLAYER_COLORS[:2])


def test_display_name_too_short_returns_422(client):
    response = join(client, display_name="A")
    assert response.status_code == 422


def test_display_name_too_long_returns_422(client):
    response = join(client, display_name="A" * 21)
    assert response.status_code == 422


def test_state_for_nonexistent_room_returns_404(client):
    response = client.get("/rooms/no-such-room/state")
    assert response.status_code == 404
