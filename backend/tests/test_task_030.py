from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.routes import rooms as rooms_module
from app.api.routes import drafts as drafts_module
from app.api.routes import submissions as submissions_module
from app.main import app
from app.models.answers import OfficialAnswers
from app.models.gameplay import (
    PlayerClueState,
    ScoreEvent,
    Submission,
    SubmissionStatus,
    utc_now,
)
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
from app.services import scoring_service
from app.services.reconciliation_service import reconcile_pending_submissions
from app.services.scoring_service import calculate_points

ROOM_ID = "room-1"
PUZZLE_ID = "puzzle-1"
CLUE_ID = "A1"
PLAYER_A = "player-a"
PLAYER_B = "player-b"
TOKEN_A = "token-room-1-player-a"
TOKEN_B = "token-room-1-player-b"
COLOR_A = "#AABBCC"
COLOR_B = "#CCBBAA"


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
        creatorId="admin-1",
    )


def make_player(player_id, color):
    return Player(
        roomId=ROOM_ID,
        playerId=player_id,
        displayName=player_id,
        color=color,
        role="player",
    )


@pytest.fixture
def env(monkeypatch):
    clue_state_repository = InMemoryPlayerClueStateRepository()
    score_repository = InMemoryScoreRepository()

    monkeypatch.setattr(
        scoring_service._default_service,
        "_player_clue_state_repository",
        clue_state_repository,
    )
    monkeypatch.setattr(
        scoring_service._default_service, "_score_repository", score_repository
    )
    monkeypatch.setattr(scoring_service._default_service, "_public_clue_states", {})

    return SimpleNamespace(
        clue_state_repository=clue_state_repository,
        score_repository=score_repository,
    )


@pytest.fixture
def api_env(env, monkeypatch):
    room_repository = InMemoryRoomRepository()
    room_repository.create(make_room())

    player_repository = InMemoryPlayerRepository()
    player_repository.add(make_player(PLAYER_A, COLOR_A))
    player_repository.add(make_player(PLAYER_B, COLOR_B))

    answer_repository = InMemoryAnswerRepository()
    answer_repository.save(
        OfficialAnswers(puzzleId=PUZZLE_ID, answers={CLUE_ID: "APPLE"})
    )

    submission_repository = InMemorySubmissionRepository()
    sessions = {
        TOKEN_A: (ROOM_ID, PLAYER_A),
        TOKEN_B: (ROOM_ID, PLAYER_B),
    }

    monkeypatch.setattr(rooms_module, "room_repository", room_repository)
    monkeypatch.setattr(rooms_module, "player_repository", player_repository)
    monkeypatch.setattr(rooms_module, "_sessions", sessions)
    monkeypatch.setattr(submissions_module, "answer_repository", answer_repository)
    monkeypatch.setattr(
        submissions_module, "submission_repository", submission_repository
    )
    monkeypatch.setattr(
        drafts_module, "player_clue_state_repository", env.clue_state_repository
    )

    return SimpleNamespace(
        room_repository=room_repository,
        player_repository=player_repository,
        answer_repository=answer_repository,
        submission_repository=submission_repository,
        clue_state_repository=env.clue_state_repository,
        score_repository=env.score_repository,
    )


@pytest.fixture
def client(api_env):
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def login_as(client, token):
    client.cookies.set("Session-Token", token)


def test_scenario_revealed_player_correct_submission_returns_zero(env):
    env.clue_state_repository.save(
        PlayerClueState(playerId=PLAYER_A, clueId=CLUE_ID, revealed=True), ROOM_ID
    )

    points = calculate_points(ROOM_ID, CLUE_ID, PLAYER_A, True, "player")

    assert points == 0


def test_scenario_unrevealed_player_first_solver_returns_two(env):
    env.clue_state_repository.save(
        PlayerClueState(playerId=PLAYER_B, clueId=CLUE_ID, revealed=False), ROOM_ID
    )

    points = calculate_points(ROOM_ID, CLUE_ID, PLAYER_B, True, "player")

    assert points == 2


def test_scenario_revealed_player_not_recorded_as_solver(api_env, client):
    api_env.clue_state_repository.save(
        PlayerClueState(playerId=PLAYER_A, clueId=CLUE_ID, revealed=True), ROOM_ID
    )
    login_as(client, TOKEN_A)

    response = client.post(
        f"/rooms/{ROOM_ID}/clues/{CLUE_ID}/submissions", json={"answer": "APPLE"}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "correct", "points": 0}
    events = api_env.score_repository.list_by_room(ROOM_ID)
    assert not any(event.playerId == PLAYER_A for event in events)
    public_state = scoring_service._default_service.get_public_clue_state(
        ROOM_ID, CLUE_ID
    )
    assert public_state.firstSolverColor is None
    assert public_state.solved is False


def test_scenario_player_a_reveal_does_not_block_player_b_first_solver(api_env, client):
    api_env.clue_state_repository.save(
        PlayerClueState(playerId=PLAYER_A, clueId=CLUE_ID, revealed=True), ROOM_ID
    )
    login_as(client, TOKEN_B)

    response = client.post(
        f"/rooms/{ROOM_ID}/clues/{CLUE_ID}/submissions", json={"answer": "APPLE"}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "correct", "points": 2}
    events = api_env.score_repository.list_by_room(ROOM_ID)
    assert len(events) == 1
    assert events[0].playerId == PLAYER_B
    assert events[0].points == 2
    public_state = scoring_service._default_service.get_public_clue_state(
        ROOM_ID, CLUE_ID
    )
    assert public_state.firstSolverColor == COLOR_B


def test_reconciliation_revealed_pending_submission_scores_zero(api_env):
    api_env.clue_state_repository.save(
        PlayerClueState(playerId=PLAYER_A, clueId=CLUE_ID, revealed=True), ROOM_ID
    )
    submission = Submission(
        submissionId="submission-pending-a",
        roomId=ROOM_ID,
        playerId=PLAYER_A,
        clueId=CLUE_ID,
        answer="APPLE",
        status=SubmissionStatus.pending,
    )
    api_env.submission_repository.add(submission)

    reconcile_pending_submissions(ROOM_ID, CLUE_ID, "APPLE")

    updated = api_env.submission_repository.get("submission-pending-a")
    assert updated.status == SubmissionStatus.correct
    assert updated.pointsAwarded == 0
    assert api_env.score_repository.list_by_room(ROOM_ID) == []


def test_edge_missing_player_clue_state_returns_two(env):
    points = calculate_points(ROOM_ID, CLUE_ID, PLAYER_B, True, "player")

    assert points == 2


def test_edge_missing_player_clue_state_after_first_solver_returns_one(env):
    env.score_repository.add_event(
        ScoreEvent(
            scoreEventId="score-existing",
            roomId=ROOM_ID,
            playerId=PLAYER_A,
            clueId=CLUE_ID,
            points=2,
            reason="correct_submission",
            timestamp=utc_now(),
        )
    )

    points = calculate_points(ROOM_ID, CLUE_ID, PLAYER_B, True, "player")

    assert points == 1
