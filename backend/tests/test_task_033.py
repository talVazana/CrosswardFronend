from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import app.services.scoring_service as scoring_service
from app.api.routes import admin as admin_module
from app.api.routes import drafts as drafts_module
from app.api.routes import rooms as rooms_module
from app.api.routes import submissions as submissions_module
from app.main import app
from app.models.answers import OfficialAnswers
from app.models.gameplay import Submission, SubmissionStatus
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Player, Room, RoomStatus
from app.repositories.in_memory import (
    InMemoryAnswerRepository,
    InMemoryPlayerClueStateRepository,
    InMemoryPlayerRepository,
    InMemoryRoomRepository,
    InMemoryScoreRepository,
    InMemorySubmissionRepository,
)
from app.services.scoring_service import ScoringService

ROOM_ID = "room-033"
PLAYER_ID = "player-033"
ADMIN_ID = "admin-033"
PLAYER_TOKEN = "token-room-033-player"
ADMIN_TOKEN = "token-room-033-admin"
PUZZLE_ID = "puzzle-033"
CLUE_ID = "A1"
OFFICIAL_ANSWER = "APPLE"


class RecordingSubmissionRepository(InMemorySubmissionRepository):
    def __init__(self):
        super().__init__()
        self.added = []

    def add(self, submission):
        self.added.append(submission)
        super().add(submission)


def make_puzzle() -> Puzzle:
    return Puzzle(
        puzzleId=PUZZLE_ID,
        title="Lifecycle Puzzle",
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
                text="Fruit clue",
                answerLength=5,
            )
        ],
    )


def make_room(status: RoomStatus = RoomStatus.active) -> Room:
    return Room(
        roomId=ROOM_ID,
        title="Lifecycle Room",
        status=status,
        puzzleSnapshot=make_puzzle(),
        creatorId=ADMIN_ID,
    )


def make_player(player_id: str, role: str = "player") -> Player:
    return Player(
        roomId=ROOM_ID,
        playerId=player_id,
        displayName=player_id,
        color="#AABBCC",
        role=role,
    )


@pytest.fixture
def env(monkeypatch):
    room_repository = InMemoryRoomRepository()
    room_repository.create(make_room(RoomStatus.active))

    player_repository = InMemoryPlayerRepository()
    player_repository.add(make_player(PLAYER_ID))
    player_repository.add(make_player(ADMIN_ID, role="admin"))

    answer_repository = InMemoryAnswerRepository()
    answer_repository.save(
        OfficialAnswers(puzzleId=PUZZLE_ID, answers={CLUE_ID: OFFICIAL_ANSWER})
    )

    submission_repository = RecordingSubmissionRepository()
    clue_state_repository = InMemoryPlayerClueStateRepository()

    monkeypatch.setattr(rooms_module, "room_repository", room_repository)
    monkeypatch.setattr(rooms_module, "player_repository", player_repository)
    monkeypatch.setattr(
        rooms_module,
        "_sessions",
        {PLAYER_TOKEN: (ROOM_ID, PLAYER_ID), ADMIN_TOKEN: (ROOM_ID, ADMIN_ID)},
    )
    monkeypatch.setattr(admin_module, "answer_repository", answer_repository)
    monkeypatch.setattr(submissions_module, "answer_repository", answer_repository)
    monkeypatch.setattr(
        submissions_module, "submission_repository", submission_repository
    )
    monkeypatch.setattr(
        drafts_module, "player_clue_state_repository", clue_state_repository
    )
    monkeypatch.setattr(drafts_module, "_player_clue_states", clue_state_repository.states)
    monkeypatch.setattr(
        scoring_service,
        "_default_service",
        ScoringService(InMemoryScoreRepository()),
    )

    with TestClient(app, base_url="https://testserver") as client:
        client.cookies.set("Session-Token", PLAYER_TOKEN)
        yield {
            "client": client,
            "room_repository": room_repository,
            "submission_repository": submission_repository,
            "clue_state_repository": clue_state_repository,
        }


def set_room_status(room_repository: InMemoryRoomRepository, status: RoomStatus) -> None:
    room = room_repository.get(ROOM_ID)
    room.status = status
    room_repository.update(room)


def submit(client: TestClient, answer: str = "apple"):
    return client.post(
        f"/rooms/{ROOM_ID}/clues/{CLUE_ID}/submissions", json={"answer": answer}
    )


def put_draft(client: TestClient, draft: str = "HELLO"):
    return client.put(
        f"/rooms/{ROOM_ID}/clues/{CLUE_ID}/draft", json={"draft": draft}
    )


def test_given_active_room_when_player_submits_then_200_ok(env):
    set_room_status(env["room_repository"], RoomStatus.active)

    response = submit(env["client"])

    assert response.status_code == 200
    assert response.json()["status"] == "correct"
    assert len(env["submission_repository"].added) == 1


def test_given_paused_room_when_player_submits_then_400_and_rejected(env):
    set_room_status(env["room_repository"], RoomStatus.paused)

    response = submit(env["client"])

    assert response.status_code == 400
    assert env["submission_repository"].added == []


def test_given_finished_room_when_player_submits_then_400_and_rejected(env):
    set_room_status(env["room_repository"], RoomStatus.finished)

    response = submit(env["client"])

    assert response.status_code == 400
    assert env["submission_repository"].added == []


def test_given_lobby_room_when_player_submits_then_400_and_rejected(env):
    set_room_status(env["room_repository"], RoomStatus.lobby)

    response = submit(env["client"])

    assert response.status_code == 400
    assert env["submission_repository"].added == []


def test_given_closed_room_when_player_submits_then_400_and_rejected(env):
    set_room_status(env["room_repository"], RoomStatus.closed)

    response = submit(env["client"])

    assert response.status_code == 400
    assert env["submission_repository"].added == []


def test_given_paused_room_when_player_saves_draft_then_200_accepted(env):
    set_room_status(env["room_repository"], RoomStatus.paused)

    response = put_draft(env["client"], "HELLO")

    assert response.status_code == 200
    saved = env["clue_state_repository"].get(ROOM_ID, PLAYER_ID, CLUE_ID)
    assert saved is not None
    assert saved.draft == "HELLO"


def test_given_finished_room_when_player_saves_draft_then_400_and_rejected(env):
    set_room_status(env["room_repository"], RoomStatus.finished)

    response = put_draft(env["client"], "HELLO")

    assert response.status_code == 400
    assert env["clue_state_repository"].get(ROOM_ID, PLAYER_ID, CLUE_ID) is None


def test_given_closed_room_when_player_saves_draft_then_400_and_rejected(env):
    set_room_status(env["room_repository"], RoomStatus.closed)

    response = put_draft(env["client"], "HELLO")

    assert response.status_code == 400
    assert env["clue_state_repository"].get(ROOM_ID, PLAYER_ID, CLUE_ID) is None


def test_given_active_room_when_player_saves_draft_then_200_accepted(env):
    set_room_status(env["room_repository"], RoomStatus.active)

    response = put_draft(env["client"], "HELLO")

    assert response.status_code == 200
    saved = env["clue_state_repository"].get(ROOM_ID, PLAYER_ID, CLUE_ID)
    assert saved is not None
    assert saved.draft == "HELLO"


def test_edge_admin_answer_update_in_finished_room_reconciles_pending_submissions(env):
    set_room_status(env["room_repository"], RoomStatus.finished)
    pending = Submission(
        submissionId="pending-finished-room",
        roomId=ROOM_ID,
        playerId=PLAYER_ID,
        clueId=CLUE_ID,
        answer="apple",
        serverTimestamp=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        status=SubmissionStatus.pending,
    )
    env["submission_repository"].add(pending)
    env["client"].cookies.set("Session-Token", ADMIN_TOKEN)

    response = env["client"].put(
        f"/admin/puzzles/{PUZZLE_ID}/clues/{CLUE_ID}/answer",
        json={"answer": OFFICIAL_ANSWER},
    )

    assert response.status_code == 200
    reconciled = env["submission_repository"].get("pending-finished-room")
    assert reconciled.status == SubmissionStatus.correct
