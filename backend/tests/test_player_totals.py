import pytest
from fastapi.testclient import TestClient

from app.api.routes import admin as admin_module
from app.api.routes import rooms as rooms_module
from app.api.routes import submissions as submissions_module
from app.main import app
from app.models.answers import OfficialAnswers
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Room, RoomStatus
from app.repositories.in_memory import (
    InMemoryAnswerRepository,
    InMemoryPlayerRepository,
    InMemoryRoomRepository,
    InMemoryScoreRepository,
)
from app.services import player_totals, scoring_service
from app.services.room_service import RoomService

ROOM_ID = "totals-room"
ROOM_ID_2 = "totals-room-2"


def make_puzzle() -> Puzzle:
    return Puzzle(
        puzzleId="puzzle_totals",
        title="Totals puzzle",
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


def make_room(room_id: str = ROOM_ID) -> Room:
    return Room(
        roomId=room_id,
        title="Totals room",
        status=RoomStatus.active,
        puzzleSnapshot=make_puzzle(),
        creatorId="creator1",
    )


@pytest.fixture
def client():
    room_repository = InMemoryRoomRepository()
    player_repository = InMemoryPlayerRepository()
    room_repository.create(make_room())
    room_repository.create(make_room(ROOM_ID_2))

    rooms_module.room_repository = room_repository
    rooms_module.player_repository = player_repository
    rooms_module.room_service = RoomService(room_repository, player_repository)
    rooms_module._sessions.clear()

    admin_module.answer_repository = InMemoryAnswerRepository()
    submissions_module.answer_repository = admin_module.answer_repository
    admin_module.answer_repository.save(
        OfficialAnswers(puzzleId="puzzle_totals", answers={"clue1": "A"})
    )

    scoring_service._default_service._score_repository = InMemoryScoreRepository()
    scoring_service._default_service._public_clue_states.clear()

    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client

    rooms_module._sessions.clear()


def solve(client, room_id: str, name: str = "Dana") -> dict:
    joined = client.post(f"/rooms/{room_id}/join", json={"displayName": name})
    assert joined.status_code == 200, joined.text
    solved = client.post(
        f"/rooms/{room_id}/clues/clue1/submissions", json={"answer": "A"}
    )
    assert solved.status_code == 200, solved.text
    return solved.json()


def test_correct_answer_creates_a_lifetime_total(client):
    solved = solve(client, ROOM_ID)

    assert solved["points"] == 2
    response = client.get("/players/Dana/total")
    assert response.status_code == 200
    assert response.json() == {"displayName": "Dana", "totalScore": 2}


def test_lifetime_total_sums_points_from_two_rooms(client):
    first = solve(client, ROOM_ID)
    second = solve(client, ROOM_ID_2)

    assert first["points"] == 2
    assert second["points"] == 2
    assert player_totals.get_total("Dana") == 4


def test_repeated_solve_in_one_room_adds_no_points(client):
    solve(client, ROOM_ID)
    again = client.post(
        f"/rooms/{ROOM_ID}/clues/clue1/submissions", json={"answer": "A"}
    )

    assert again.status_code == 200
    assert again.json()["points"] == 0
    assert player_totals.get_total("Dana") == 2


def test_totals_are_kept_after_the_room_is_deleted(client):
    solve(client, ROOM_ID)

    rooms_module.room_repository = InMemoryRoomRepository()
    rooms_module.room_repository.create(make_room(ROOM_ID_2))

    assert client.get(f"/rooms/{ROOM_ID}/state").status_code == 404
    assert player_totals.get_total("Dana") == 2


def test_leaderboard_sorts_by_total_score(client):
    solve(client, ROOM_ID, name="Dana")
    solve(client, ROOM_ID_2, name="Amit")

    response = client.get("/players/totals")

    assert response.status_code == 200
    players = response.json()["players"]
    assert players[0]["displayName"] == "Amit"
    assert players[0]["totalScore"] == 2
    assert players[0]["color"] == "#0D9488"
    assert players[1]["displayName"] == "Dana"
    assert players[1]["totalScore"] == 2
    assert players[1]["color"] == "#DC2626"


def test_unknown_name_has_zero_total(client):
    response = client.get("/players/NoOne/total")

    assert response.status_code == 200
    assert response.json()["totalScore"] == 0
