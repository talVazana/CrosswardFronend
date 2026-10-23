from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import app.services.scoring_service as scoring_service
from app.api.routes import admin as admin_module
from app.api.routes import rooms as rooms_module
from app.api.routes import submissions as submissions_module
from app.main import app
from app.models.gameplay import Submission, SubmissionStatus
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Player, Room, RoomStatus
from app.repositories.in_memory import (
    InMemoryAnswerRepository,
    InMemoryPlayerRepository,
    InMemoryRoomRepository,
    InMemoryScoreRepository,
    InMemorySubmissionRepository,
)
from app.services.reconciliation_service import reconcile_pending_submissions
from app.services.scoring_service import ScoringService

ROOM_ID = "room-1"
PUZZLE_ID = "puzzle-1"
CLUE_ID = "A1"
ADMIN_ID = "admin-1"
ADMIN_TOKEN = "token-room-1-admin-1"

T1 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 1, 1, 10, 0, 1, tzinfo=timezone.utc)
T3 = datetime(2026, 1, 1, 10, 0, 2, tzinfo=timezone.utc)


def make_submission(submission_id, player_id, answer, timestamp, status=SubmissionStatus.pending):
    return Submission(
        submissionId=submission_id,
        roomId=ROOM_ID,
        playerId=player_id,
        clueId=CLUE_ID,
        answer=answer,
        serverTimestamp=timestamp,
        status=status,
    )


def make_player(player_id, role="player"):
    return Player(
        roomId=ROOM_ID,
        playerId=player_id,
        displayName=player_id,
        color="#AABBCC",
        role=role,
    )


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
                clueId=CLUE_ID,
                number=1,
                direction="across",
                text="Fruit clue",
                answerLength=5,
            )
        ],
    )


def make_room():
    return Room(
        roomId=ROOM_ID,
        title="Test Room",
        status=RoomStatus.active,
        puzzleSnapshot=make_puzzle(),
        creatorId=ADMIN_ID,
    )


@pytest.fixture
def repositories(monkeypatch):
    submission_repository = InMemorySubmissionRepository()
    player_repository = InMemoryPlayerRepository()
    for player_id in ("player-a", "player-b", "player-c"):
        player_repository.add(make_player(player_id))

    monkeypatch.setattr(submissions_module, "submission_repository", submission_repository)
    monkeypatch.setattr(rooms_module, "player_repository", player_repository)
    monkeypatch.setattr(
        scoring_service,
        "_default_service",
        ScoringService(InMemoryScoreRepository()),
    )
    return submission_repository, player_repository


@pytest.fixture
def admin_client(repositories, monkeypatch):
    submission_repository, player_repository = repositories
    player_repository.add(make_player(ADMIN_ID, role="admin"))

    room_repository = InMemoryRoomRepository()
    room_repository.create(make_room())
    answer_repository = InMemoryAnswerRepository()

    monkeypatch.setattr(rooms_module, "room_repository", room_repository)
    monkeypatch.setattr(rooms_module, "_sessions", {ADMIN_TOKEN: (ROOM_ID, ADMIN_ID)})
    monkeypatch.setattr(admin_module, "answer_repository", answer_repository)
    monkeypatch.setattr(submissions_module, "answer_repository", answer_repository)

    with TestClient(app, base_url="https://testserver") as client:
        client.cookies.set("Session-Token", ADMIN_TOKEN)
        yield client, submission_repository, answer_repository


def test_scenario_three_pending_in_chronological_order_scores_2_1_and_incorrect_0(repositories):
    submission_repository, _ = repositories
    player_a = make_submission("sub-a", "player-a", "banana", T1)
    player_b = make_submission("sub-b", "player-b", "apple", T2)
    player_c = make_submission("sub-c", "player-c", "  APPLE ", T3)
    for submission in (player_c, player_a, player_b):
        submission_repository.add(submission)

    reconcile_pending_submissions(ROOM_ID, CLUE_ID, "APPLE")

    stored_a = submission_repository.get("sub-a")
    stored_b = submission_repository.get("sub-b")
    stored_c = submission_repository.get("sub-c")
    assert stored_a.status == SubmissionStatus.incorrect
    assert stored_a.pointsAwarded == 0
    assert stored_b.status == SubmissionStatus.correct
    assert stored_b.pointsAwarded == 2
    assert stored_c.status == SubmissionStatus.correct
    assert stored_c.pointsAwarded == 1


def test_scenario_admin_put_hook_resolves_all_pending_submissions(admin_client):
    client, submission_repository, answer_repository = admin_client
    submission_repository.add(make_submission("sub-a", "player-a", "BANANA", T1))
    submission_repository.add(make_submission("sub-b", "player-b", "apple", T2))
    submission_repository.add(make_submission("sub-c", "player-c", "APPLE", T3))

    response = client.put(
        f"/admin/puzzles/{PUZZLE_ID}/clues/{CLUE_ID}/answer",
        json={"answer": "  apple  "},
    )

    assert response.status_code == 200
    assert answer_repository.get(PUZZLE_ID).answers[CLUE_ID] == "APPLE"
    stored_a = submission_repository.get("sub-a")
    stored_b = submission_repository.get("sub-b")
    stored_c = submission_repository.get("sub-c")
    assert stored_a.status == SubmissionStatus.incorrect
    assert stored_a.pointsAwarded == 0
    assert stored_b.status == SubmissionStatus.correct
    assert stored_b.pointsAwarded == 2
    assert stored_c.status == SubmissionStatus.correct
    assert stored_c.pointsAwarded == 1


def test_edge_empty_pending_list_reconciles_without_errors(repositories):
    submission_repository, _ = repositories

    reconcile_pending_submissions(ROOM_ID, CLUE_ID, "APPLE")

    assert submission_repository.list_pending_by_room(ROOM_ID) == []


def test_edge_millisecond_timestamp_differences_are_strictly_respected(repositories):
    submission_repository, _ = repositories
    later = make_submission(
        "sub-later",
        "player-later",
        "APPLE",
        datetime(2026, 1, 1, 10, 0, 0, 1000, tzinfo=timezone.utc),
    )
    earlier = make_submission(
        "sub-earlier",
        "player-earlier",
        "APPLE",
        datetime(2026, 1, 1, 10, 0, 0, 0, tzinfo=timezone.utc),
    )
    submission_repository.add(later)
    submission_repository.add(earlier)

    reconcile_pending_submissions(ROOM_ID, CLUE_ID, "APPLE")

    assert submission_repository.get("sub-earlier").pointsAwarded == 2
    assert submission_repository.get("sub-later").pointsAwarded == 1


def test_edge_already_non_pending_submissions_are_ignored(repositories):
    submission_repository, _ = repositories
    submission_repository.add(
        make_submission(
            "sub-correct", "player-a", "APPLE", T1, status=SubmissionStatus.correct
        )
    )
    submission_repository.add(make_submission("sub-pending", "player-b", "APPLE", T2))

    reconcile_pending_submissions(ROOM_ID, CLUE_ID, "APPLE")

    unchanged = submission_repository.get("sub-correct")
    assert unchanged.status == SubmissionStatus.correct
    assert unchanged.pointsAwarded == 0
    assert submission_repository.get("sub-pending").pointsAwarded == 2
