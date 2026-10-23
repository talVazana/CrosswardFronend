from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.routes import admin as admin_module
from app.api.routes import rooms as rooms_module
from app.api.routes import submissions as submissions_module
from app.main import app
from app.models.answers import OfficialAnswers
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Player, Room, RoomStatus
from app.repositories.in_memory import (
    InMemoryAnswerRepository,
    InMemoryPlayerRepository,
    InMemoryRoomRepository,
    InMemorySubmissionRepository,
)

ROOM_ID = "room-1"
PLAYER_ID = "player-1"
TOKEN = "token-room-1-player-1"
PUZZLE_ID = "puzzle-1"
OFFICIAL_ANSWERS = {"A1": "APPLE"}


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


def make_room() -> Room:
    return Room(
        roomId=ROOM_ID,
        title="Test Room",
        status=RoomStatus.active,
        puzzleSnapshot=make_puzzle(),
        creatorId="creator-1",
    )


def make_player() -> Player:
    return Player(
        roomId=ROOM_ID,
        playerId=PLAYER_ID,
        displayName="Alice",
        color="#AABBCC",
        role="player",
    )


@pytest.fixture
def client():
    room_repository = InMemoryRoomRepository()
    room_repository.create(make_room())

    player_repository = InMemoryPlayerRepository()
    player_repository.add(make_player())

    answer_repository = InMemoryAnswerRepository()
    answer_repository.save(
        OfficialAnswers(puzzleId=PUZZLE_ID, answers=dict(OFFICIAL_ANSWERS))
    )

    submission_repository = RecordingSubmissionRepository()

    rooms_module.room_repository = room_repository
    rooms_module.player_repository = player_repository
    rooms_module._sessions.clear()
    rooms_module._sessions[TOKEN] = (ROOM_ID, PLAYER_ID)

    admin_module.answer_repository = answer_repository
    submissions_module.answer_repository = answer_repository
    submissions_module.submission_repository = submission_repository

    with TestClient(app, base_url="https://testserver") as test_client:
        test_client.cookies.set("Session-Token", TOKEN)
        yield test_client, submission_repository

    rooms_module._sessions.clear()


def submit_answer(client, clue_id="A1", answer="apple", **extra):
    payload = {"answer": answer}
    payload.update(extra)
    return client.post(
        f"/rooms/{ROOM_ID}/clues/{clue_id}/submissions", json=payload
    )


def assert_utc_aware(value):
    assert isinstance(value, datetime)
    assert value.tzinfo is not None
    assert value.utcoffset() == timedelta(0)


def test_correct_answer_returns_200_and_status_correct(client):
    test_client, _ = client

    response = submit_answer(test_client, "A1", "apple")

    assert response.status_code == 200
    assert response.json() == {"status": "correct"}


def test_incorrect_answer_returns_200_and_status_incorrect(client):
    test_client, _ = client

    response = submit_answer(test_client, "A1", "ORANGE")

    assert response.status_code == 200
    assert response.json() == {"status": "incorrect"}


def test_clue_without_official_answer_returns_200_and_status_pending(client):
    test_client, _ = client

    response = submit_answer(test_client, "D1", "PEAR")

    assert response.status_code == 200
    assert response.json() == {"status": "pending"}


def test_no_official_answers_at_all_returns_200_and_status_pending(client):
    test_client, _ = client
    submissions_module.answer_repository = InMemoryAnswerRepository()

    response = submit_answer(test_client, "A1", "APPLE")

    assert response.status_code == 200
    assert response.json() == {"status": "pending"}


def test_saved_submission_has_server_utc_timestamp_and_zero_points(client):
    test_client, submission_repository = client
    before = datetime.now(timezone.utc)

    response = submit_answer(test_client, "A1", "apple")

    after = datetime.now(timezone.utc)
    assert response.status_code == 200
    assert response.json() == {"status": "correct"}
    assert len(submission_repository.added) == 1

    saved = submission_repository.added[0]
    assert_utc_aware(saved.serverTimestamp)
    assert before <= saved.serverTimestamp <= after
    assert saved.pointsAwarded == 0
    assert saved.status.value == "correct"
    assert saved.roomId == ROOM_ID
    assert saved.playerId == PLAYER_ID
    assert saved.clueId == "A1"
    assert saved.answer == "apple"


def test_padded_and_mixed_case_answer_evaluates_correct(client):
    test_client, _ = client

    response = submit_answer(test_client, "A1", "  aPpLe  ")

    assert response.status_code == 200
    assert response.json() == {"status": "correct"}


def test_excessive_whitespace_and_nbsp_normalize_to_correct(client):
    test_client, _ = client

    response = submit_answer(test_client, "A1", "\t\u00a0 APPLE \u00a0\n")

    assert response.status_code == 200
    assert response.json() == {"status": "correct"}


def test_special_characters_that_do_not_normalize_to_answer_are_incorrect(client):
    test_client, _ = client

    response = submit_answer(test_client, "A1", "APPLE!!!")

    assert response.status_code == 200
    assert response.json() == {"status": "incorrect"}


def test_client_supplied_timestamp_is_ignored(client):
    test_client, submission_repository = client
    before = datetime.now(timezone.utc)

    response = submit_answer(
        test_client,
        "A1",
        "apple",
        serverTimestamp="2000-01-01T00:00:00Z",
        timestamp="2000-01-01T00:00:00Z",
    )

    after = datetime.now(timezone.utc)
    assert response.status_code == 200
    assert len(submission_repository.added) == 1

    saved = submission_repository.added[0]
    assert_utc_aware(saved.serverTimestamp)
    assert before <= saved.serverTimestamp <= after


def test_client_supplied_status_and_points_are_ignored(client):
    test_client, submission_repository = client

    response = submit_answer(
        test_client, "A1", "ORANGE", status="correct", pointsAwarded=100
    )

    assert response.status_code == 200
    assert response.json() == {"status": "incorrect"}
    saved = submission_repository.added[0]
    assert saved.status.value == "incorrect"
    assert saved.pointsAwarded == 0
