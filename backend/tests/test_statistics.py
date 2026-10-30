import pytest
from fastapi.testclient import TestClient

import jwt

import app.services.scoring_service as scoring_service
from app.api.routes import admin as admin_module
from app.api.routes import drafts as drafts_module
from app.api.routes import gameplay as gameplay_module
from app.api.routes import rooms as rooms_module
from app.api.routes import submissions as submissions_module
from app.main import app
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import ASSIGNED_PLAYER_COLORS, Player, Room, RoomStatus
from app.repositories.in_memory import (
    InMemoryAnswerRepository,
    InMemoryPlayerClueStateRepository,
    InMemoryPlayerRepository,
    InMemoryRoomRepository,
    InMemoryScoreRepository,
    InMemorySubmissionRepository,
)
from app.services.scoring_service import ScoringService

ROOM_ID = "stat-room"
PUZZLE_ID = "stat-puzzle"
CLUE_ID = "A1"
ANSWER = "APPLE"
PLAYER_A = "player-a"
PLAYER_B = "player-b"
ADMIN = "admin-1"
TOKEN_A = "token-a"


def make_puzzle() -> Puzzle:
    return Puzzle(
        puzzleId=PUZZLE_ID,
        title="Stats Puzzle",
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
                clueId=CLUE_ID,
                number=1,
                direction="across",
                text="Fruit",
                answerLength=5,
            )
        ],
    )


def make_room() -> Room:
    return Room(
        roomId=ROOM_ID,
        title="Stats Room",
        status=RoomStatus.active,
        puzzleSnapshot=make_puzzle(),
        creatorId=ADMIN,
    )


def make_player(player_id: str, color: str, role: str = "player") -> Player:
    return Player(
        roomId=ROOM_ID,
        playerId=player_id,
        displayName=player_id,
        color=color,
        role=role,
    )


@pytest.fixture
def env(monkeypatch):
    room_repository = InMemoryRoomRepository()
    room_repository.create(make_room())

    player_repository = InMemoryPlayerRepository()
    player_repository.add(make_player(PLAYER_A, ASSIGNED_PLAYER_COLORS[0]))
    player_repository.add(make_player(PLAYER_B, ASSIGNED_PLAYER_COLORS[1]))
    player_repository.add(make_player(ADMIN, "#000000", role="admin"))

    answer_repository = InMemoryAnswerRepository()
    submission_repository = InMemorySubmissionRepository()
    clue_state_repository = InMemoryPlayerClueStateRepository()
    score_service = ScoringService(InMemoryScoreRepository())

    monkeypatch.setattr(rooms_module, "room_repository", room_repository)
    monkeypatch.setattr(rooms_module, "player_repository", player_repository)
    monkeypatch.setattr(rooms_module, "_sessions", {TOKEN_A: (ROOM_ID, PLAYER_A)})
    monkeypatch.setattr(admin_module, "answer_repository", answer_repository)
    monkeypatch.setattr(submissions_module, "answer_repository", answer_repository)
    monkeypatch.setattr(gameplay_module, "answer_repository", answer_repository)
    monkeypatch.setattr(submissions_module, "submission_repository", submission_repository)
    monkeypatch.setattr(submissions_module, "_clue_locks", {})
    monkeypatch.setattr(drafts_module, "player_clue_state_repository", clue_state_repository)
    monkeypatch.setattr(gameplay_module, "player_clue_state_repository", clue_state_repository)
    monkeypatch.setattr(drafts_module, "_player_clue_states", clue_state_repository.states)
    monkeypatch.setattr(scoring_service, "_default_service", score_service)

    with TestClient(app, base_url="https://testserver") as client:
        yield {"client": client}


def as_player(client: TestClient, token: str) -> None:
    client.cookies.set(rooms_module.SESSION_COOKIE_NAME, token)


def as_admin(client: TestClient) -> None:
    token = jwt.encode(
        {"email": "shachar383838@gmail.com"}, "test-secret", algorithm="HS256"
    )
    response = client.post(
        "/admin/session", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text


def approve(client: TestClient, answer: str = ANSWER):
    as_admin(client)
    response = client.put(
        f"/admin/puzzles/{PUZZLE_ID}/clues/{CLUE_ID}/answer",
        json={"answer": answer},
    )
    assert response.status_code == 200, response.text


def statistics(client: TestClient) -> dict:
    response = client.get(f"/rooms/{ROOM_ID}/statistics")
    assert response.status_code == 200, response.text
    return response.json()


def test_admin_first_solve_counts_admin_and_not_players(env):
    client = env["client"]
    approve(client)

    stats = statistics(client)

    assert stats["adminTotal"] == 1
    assert stats["adminSolvedClues"] == 1
    assert stats["playersTotal"] == 0
    names = {entry["displayName"]: entry["solvedClues"] for entry in stats["players"]}
    assert names[PLAYER_A] == 0
    assert names[PLAYER_B] == 0


def test_approving_pending_player_submission_credits_player_not_admin(env):
    client = env["client"]
    as_player(client, TOKEN_A)
    pending = client.post(
        f"/rooms/{ROOM_ID}/clues/{CLUE_ID}/submissions", json={"answer": ANSWER}
    )
    assert pending.status_code == 200, pending.text
    assert pending.json() == {"status": "pending"}

    approve(client)

    stats = statistics(client)
    assert stats["adminTotal"] == 0
    assert stats["adminSolvedClues"] == 0
    assert stats["playersTotal"] == 1
    names = {entry["displayName"]: entry["solvedClues"] for entry in stats["players"]}
    assert names[PLAYER_A] == 1
    assert names[PLAYER_B] == 0


def test_statistics_endpoint_shape(env):
    client = env["client"]

    stats = statistics(client)

    assert set(stats.keys()) == {
        "players",
        "adminSolvedClues",
        "playersTotal",
        "adminTotal",
    }
    for entry in stats["players"]:
        assert set(entry.keys()) == {"playerId", "displayName", "color", "solvedClues"}


def test_admin_solve_is_idempotent_on_repeat_approve(env):
    client = env["client"]
    approve(client)
    approve(client)

    stats = statistics(client)
    assert stats["adminTotal"] == 1
