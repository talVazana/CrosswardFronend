import pytest
from fastapi.testclient import TestClient

from app.api.routes import drafts as drafts_module
from app.api.routes import rooms as rooms_module
from app.main import app
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Player, Room, RoomStatus
from app.repositories.in_memory import InMemoryPlayerRepository, InMemoryRoomRepository
from app.services.room_service import RoomService

ROOM_ID = "room-1"
OTHER_ROOM_ID = "room-2"
PLAYER_A = "player-A"
PLAYER_B = "player-B"


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
                clueId="A1",
                number=1,
                direction="across",
                text="Secret clue",
                answerLength=5,
            )
        ],
    )


def make_room(room_id: str = ROOM_ID) -> Room:
    return Room(
        roomId=room_id,
        title="Test Room",
        status=RoomStatus.lobby,
        puzzleSnapshot=make_puzzle(),
        creatorId="creator1",
    )


def make_player(room_id: str, player_id: str, display_name: str) -> Player:
    return Player(
        roomId=room_id,
        playerId=player_id,
        displayName=display_name,
        color="#AABBCC",
        role="player",
    )


@pytest.fixture
def client():
    room_repository = InMemoryRoomRepository()
    player_repository = InMemoryPlayerRepository()
    room_repository.create(make_room(ROOM_ID))
    room_repository.create(make_room(OTHER_ROOM_ID))
    player_repository.add(make_player(ROOM_ID, PLAYER_A, "Alice"))
    player_repository.add(make_player(ROOM_ID, PLAYER_B, "Bob"))

    rooms_module.room_repository = room_repository
    rooms_module.player_repository = player_repository
    rooms_module.room_service = RoomService(room_repository, player_repository)
    rooms_module._sessions.clear()
    drafts_module._player_clue_states.clear()

    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client

    rooms_module._sessions.clear()
    drafts_module._player_clue_states.clear()


def authenticate(client: TestClient, player_id: str, room_id: str = ROOM_ID) -> str:
    token = f"token-{room_id}-{player_id}"
    rooms_module._sessions[token] = (room_id, player_id)
    client.cookies.set("Session-Token", token)
    return token


def put_draft(client: TestClient, clue_id: str = "A1", draft: str = "HELLO", room_id: str = ROOM_ID):
    return client.put(f"/rooms/{room_id}/clues/{clue_id}/draft", json={"draft": draft})


def get_drafts(client: TestClient, room_id: str = ROOM_ID):
    return client.get(f"/rooms/{room_id}/drafts")


def test_put_draft_with_valid_session_returns_200(client):
    authenticate(client, PLAYER_A)
    response = put_draft(client)
    assert response.status_code == 200


def test_put_draft_updates_server_state_for_player_and_clue(client):
    authenticate(client, PLAYER_A)
    put_draft(client, clue_id="A1", draft="HELLO")

    state = drafts_module._player_clue_states[(ROOM_ID, PLAYER_A, "A1")]
    assert state.playerId == PLAYER_A
    assert state.clueId == "A1"
    assert state.draft == "HELLO"


def test_get_drafts_returns_200_and_dictionary_with_saved_draft(client):
    authenticate(client, PLAYER_A)
    put_draft(client, clue_id="A1", draft="HELLO")

    response = get_drafts(client)
    assert response.status_code == 200
    assert response.json() == {"A1": "HELLO"}


def test_get_drafts_returns_dictionary_not_list(client):
    authenticate(client, PLAYER_A)
    put_draft(client, clue_id="A1", draft="HELLO")

    body = get_drafts(client).json()
    assert isinstance(body, dict)
    assert not isinstance(body, list)


def test_get_drafts_returns_only_current_player_drafts(client):
    authenticate(client, PLAYER_A)
    put_draft(client, clue_id="A1", draft="HELLO")
    client.cookies.clear()

    authenticate(client, PLAYER_B)
    put_draft(client, clue_id="A1", draft="BOB")
    put_draft(client, clue_id="D1", draft="DOWN")

    body = get_drafts(client).json()
    assert body == {"A1": "BOB", "D1": "DOWN"}


def test_put_draft_without_session_cookie_returns_401(client):
    response = put_draft(client)
    assert response.status_code == 401


def test_get_drafts_without_session_cookie_returns_401(client):
    response = get_drafts(client)
    assert response.status_code == 401


def test_put_draft_with_invalid_session_cookie_returns_401(client):
    client.cookies.set("Session-Token", "not-a-real-token")
    response = put_draft(client)
    assert response.status_code == 401


def test_get_drafts_with_invalid_session_cookie_returns_401(client):
    client.cookies.set("Session-Token", "not-a-real-token")
    response = get_drafts(client)
    assert response.status_code == 401


def test_put_draft_longer_than_100_chars_returns_422(client):
    authenticate(client, PLAYER_A)
    response = put_draft(client, clue_id="A1", draft="A" * 101)
    assert response.status_code == 422


def test_put_draft_empty_string_clears_existing_draft(client):
    authenticate(client, PLAYER_A)
    first = put_draft(client, clue_id="A1", draft="HELLO")
    assert first.status_code == 200

    cleared = put_draft(client, clue_id="A1", draft="")
    assert cleared.status_code == 200

    state = drafts_module._player_clue_states[(ROOM_ID, PLAYER_A, "A1")]
    assert state.draft == ""
    assert get_drafts(client).json() == {"A1": ""}
