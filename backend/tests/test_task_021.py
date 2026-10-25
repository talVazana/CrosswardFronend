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
PLAYER_A = "player-A"
PLAYER_B = "player-B"
ADMIN = "admin-1"
TOKEN_A = "token-room-1-player-A"
TOKEN_B = "token-room-1-player-B"
TOKEN_ADMIN = "token-room-1-admin-1"


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


def make_player(room_id: str, player_id: str, display_name: str, role: str = "player") -> Player:
    return Player(
        roomId=room_id,
        playerId=player_id,
        displayName=display_name,
        color="#AABBCC",
        role=role,
    )


@pytest.fixture
def clients():
    room_repository = InMemoryRoomRepository()
    player_repository = InMemoryPlayerRepository()
    room_repository.create(make_room())
    player_repository.add(make_player(ROOM_ID, PLAYER_A, "Alice"))
    player_repository.add(make_player(ROOM_ID, PLAYER_B, "Bob"))
    player_repository.add(make_player(ROOM_ID, ADMIN, "Admin", role="admin"))

    rooms_module.room_repository = room_repository
    rooms_module.player_repository = player_repository
    rooms_module.room_service = RoomService(room_repository, player_repository)
    rooms_module._sessions.clear()
    rooms_module._sessions[TOKEN_A] = (ROOM_ID, PLAYER_A)
    rooms_module._sessions[TOKEN_B] = (ROOM_ID, PLAYER_B)
    rooms_module._sessions[TOKEN_ADMIN] = (ROOM_ID, ADMIN)
    drafts_module._player_clue_states.clear()

    with TestClient(app, base_url="https://testserver") as client_a, TestClient(
        app, base_url="https://testserver"
    ) as client_b, TestClient(app, base_url="https://testserver") as client_admin:
        client_a.cookies.set("Session-Token", TOKEN_A)
        client_b.cookies.set("Session-Token", TOKEN_B)
        client_admin.cookies.set("Session-Token", TOKEN_ADMIN)
        yield client_a, client_b, client_admin

    rooms_module._sessions.clear()
    drafts_module._player_clue_states.clear()


def put_draft(client: TestClient, clue_id: str, draft: str):
    return client.put(f"/rooms/{ROOM_ID}/clues/{clue_id}/draft", json={"draft": draft})


def get_drafts(client: TestClient):
    return client.get(f"/rooms/{ROOM_ID}/drafts")


def get_public_state(client: TestClient):
    return client.get(f"/rooms/{ROOM_ID}/state")


def find_strings(node):
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            found.append(str(key))
            found.extend(find_strings(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(find_strings(item))
    elif isinstance(node, str):
        found.append(node)
    return found


def test_player_a_receives_exactly_their_own_data(clients):
    client_a, _, _ = clients
    assert put_draft(client_a, "A1", "APPLE").status_code == 200

    response = get_drafts(client_a)
    assert response.status_code == 200
    assert response.json() == {"A1": "APPLE"}


def test_player_b_drafts_empty_and_do_not_contain_player_a_apple(clients):
    client_a, client_b, _ = clients
    assert put_draft(client_a, "A1", "APPLE").status_code == 200

    response = get_drafts(client_b)
    assert response.status_code == 200
    assert response.json() == {}
    assert "APPLE" not in response.text


def test_player_b_put_does_not_override_player_a_draft(clients):
    client_a, client_b, _ = clients
    assert put_draft(client_a, "A1", "APPLE").status_code == 200
    assert put_draft(client_b, "A1", "BANANA").status_code == 200

    response = get_drafts(client_a)
    assert response.status_code == 200
    assert response.json() == {"A1": "APPLE"}


def test_crafted_request_cannot_retrieve_other_player_draft(clients):
    client_a, _, _ = clients
    assert put_draft(clients[1], "A1", "BANANA").status_code == 200

    response = client_a.get(f"/rooms/{ROOM_ID}/drafts?playerId={PLAYER_B}")
    assert response.status_code == 200
    assert "BANANA" not in response.text
    assert response.json() == {}


def test_public_state_contains_no_draft_strings(clients):
    client_a, client_b, client_admin = clients
    assert put_draft(client_a, "A1", "APPLE").status_code == 200
    assert put_draft(client_b, "A1", "BANANA").status_code == 200

    for client in (client_a, client_b, client_admin):
        response = get_public_state(client)
        assert response.status_code == 200
        body = response.json()
        text = response.text
        assert "APPLE" not in text
        assert "BANANA" not in text
        for value in find_strings(body):
            assert value.lower() not in {"apple", "banana"}
        for key in find_strings(body):
            assert "draft" not in key.lower()


def test_admin_public_state_contains_no_private_player_drafts(clients):
    client_a, _, client_admin = clients
    assert put_draft(client_a, "A1", "APPLE").status_code == 200

    response = get_public_state(client_admin)
    assert response.status_code == 200
    body = response.json()
    assert "APPLE" not in response.text
    assert all("draft" not in key.lower() for key in find_strings(body))
