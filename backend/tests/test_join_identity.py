import pytest
from fastapi.testclient import TestClient

from app.api.routes import rooms as rooms_module
from app.main import app
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Room, RoomStatus
from app.repositories.in_memory import InMemoryPlayerRepository, InMemoryRoomRepository
from app.services.room_service import RoomService

ROOM_ID = "test-room"


def make_puzzle() -> Puzzle:
    return Puzzle(
        puzzleId="puzzle_test",
        title="Join puzzle",
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
                text="Clue",
                answerLength=1,
            )
        ],
    )


@pytest.fixture
def client():
    room_repository = InMemoryRoomRepository()
    player_repository = InMemoryPlayerRepository()
    room_repository.create(
        Room(
            roomId=ROOM_ID,
            title="Test Room",
            status=RoomStatus.active,
            puzzleSnapshot=make_puzzle(),
            creatorId="creator1",
        )
    )

    rooms_module.room_repository = room_repository
    rooms_module.player_repository = player_repository
    rooms_module.room_service = RoomService(room_repository, player_repository)
    rooms_module._sessions.clear()

    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client

    rooms_module._sessions.clear()


def test_rejoin_with_same_name_returns_same_player(client):
    first = client.post(f"/rooms/{ROOM_ID}/join", json={"displayName": "Dana"})
    second = client.post(f"/rooms/{ROOM_ID}/join", json={"displayName": "dana"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["playerId"] == second.json()["playerId"]

    players = client.get(f"/rooms/{ROOM_ID}/state").json()["players"]
    assert len(players) == 1


def test_rejoin_with_different_name_creates_new_player(client):
    first = client.post(f"/rooms/{ROOM_ID}/join", json={"displayName": "Dana"})
    second = client.post(f"/rooms/{ROOM_ID}/join", json={"displayName": "Noam"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["playerId"] != second.json()["playerId"]

    players = client.get(f"/rooms/{ROOM_ID}/state").json()["players"]
    names = sorted(player["displayName"] for player in players)
    assert names == ["Dana", "Noam"]
