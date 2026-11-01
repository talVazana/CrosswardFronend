import threading
from concurrent.futures import ThreadPoolExecutor

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
    InMemoryScoreRepository,
    InMemorySubmissionRepository,
)
from app.services import scoring_service as scoring_module
from app.services.scoring_service import ScoringService

ROOM_ID = "room-27"
CLUE_ID = "A1"
PUZZLE_ID = "puzzle-27"
OFFICIAL_ANSWER = "APPLE"
URL = f"/rooms/{ROOM_ID}/clues/{CLUE_ID}/submissions"
PLAYER_COUNT = 10


def make_puzzle() -> Puzzle:
    return Puzzle(
        puzzleId=PUZZLE_ID,
        title="Concurrency Puzzle",
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


def make_room() -> Room:
    return Room(
        roomId=ROOM_ID,
        title="Concurrency Room",
        status=RoomStatus.active,
        puzzleSnapshot=make_puzzle(),
        creatorId="creator-1",
    )


@pytest.fixture
def env():
    room_repository = InMemoryRoomRepository()
    room_repository.create(make_room())

    player_repository = InMemoryPlayerRepository()
    answer_repository = InMemoryAnswerRepository()
    answer_repository.save(
        OfficialAnswers(puzzleId=PUZZLE_ID, answers={CLUE_ID: OFFICIAL_ANSWER})
    )

    players = {}
    for index in range(PLAYER_COUNT):
        player_id = f"player-{index}"
        color = f"#AABB{index:02X}"
        player_repository.add(
            Player(
                roomId=ROOM_ID,
                playerId=player_id,
                displayName=f"Player {index}",
                color=color,
                role="player",
            )
        )
        players[player_id] = {"token": f"token-{player_id}", "color": color}

    submission_repository = InMemorySubmissionRepository()
    score_service = ScoringService(InMemoryScoreRepository())

    rooms_module.room_repository = room_repository
    rooms_module.player_repository = player_repository
    rooms_module._sessions.clear()
    for player_id, info in players.items():
        rooms_module._sessions[info["token"]] = (ROOM_ID, player_id)

    admin_module.answer_repository = answer_repository
    submissions_module.answer_repository = answer_repository
    submissions_module.submission_repository = submission_repository
    submissions_module._clue_locks = {}
    scoring_module._default_service = score_service

    with TestClient(app, base_url="https://testserver") as client:
        yield client, players, score_service, submission_repository

    rooms_module._sessions.clear()
    submissions_module._clue_locks = {}


def fire_concurrently(client, player_ids, players):
    barrier = threading.Barrier(len(player_ids))
    timeout = 15

    def worker(player_id):
        barrier.wait(timeout=timeout)
        return client.post(
            URL,
            json={"answer": OFFICIAL_ANSWER},
            cookies={rooms_module.SESSION_COOKIE_NAME: players[player_id]["token"]},
        )

    with ThreadPoolExecutor(max_workers=len(player_ids)) as pool:
        futures = [pool.submit(worker, player_id) for player_id in player_ids]
        responses = [future.result(timeout=timeout) for future in futures]
    return responses


def points_by_player(player_ids, responses):
    result = {}
    for player_id, response in zip(player_ids, responses):
        assert response.status_code == 200, (
            f"{player_id} got status {response.status_code}: {response.text}"
        )
        body = response.json()
        assert body.get("status") == "correct", f"{player_id} body: {body}"
        result[player_id] = body.get("points")
    return result


def test_two_different_players_concurrent_each_gets_one(env):
    client, players, score_service, _ = env
    player_ids = ["player-0", "player-1"]

    responses = fire_concurrently(client, player_ids, players)
    points = points_by_player(player_ids, responses)

    assert sorted(points.values()) == [1, 1]
    assert sum(points.values()) == 2

    state = score_service.get_public_clue_state(ROOM_ID, CLUE_ID)
    assert state.solved is True
    assert state.firstSolverColor in {players[pid]["color"] for pid in player_ids}


def test_same_player_duplicate_concurrent_first_gets_one_second_gets_zero(env):
    client, players, score_service, _ = env
    player_ids = ["player-0", "player-0"]

    responses = fire_concurrently(client, player_ids, players)
    points = [response.json().get("points") for response in responses]

    for response in responses:
        assert response.status_code == 200, response.text
        assert response.json().get("status") == "correct", response.text

    assert sorted(points) == [0, 1]
    assert sum(points) == 1

    state = score_service.get_public_clue_state(ROOM_ID, CLUE_ID)
    assert state.solved is True
    assert state.firstSolverColor == players["player-0"]["color"]


def test_high_concurrency_ten_players_each_gets_one(env):
    client, players, score_service, _ = env
    player_ids = [f"player-{index}" for index in range(PLAYER_COUNT)]

    responses = fire_concurrently(client, player_ids, players)
    points = points_by_player(player_ids, responses)

    assert list(points.values()).count(1) == PLAYER_COUNT
    assert sum(points.values()) == PLAYER_COUNT

    state = score_service.get_public_clue_state(ROOM_ID, CLUE_ID)
    assert state.solved is True
    assert state.firstSolverColor in {players[pid]["color"] for pid in player_ids}
