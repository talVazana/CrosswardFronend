from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.routes import drafts as drafts_module
from app.api.routes import gameplay as gameplay_module
from app.api.routes import rooms as rooms_module
from app.main import app
from app.models.answers import OfficialAnswers
from app.models.gameplay import PlayerClueState
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Player, Room, RoomStatus
from app.repositories.in_memory import (
    InMemoryAnswerRepository,
    InMemoryPlayerClueStateRepository,
    InMemoryPlayerRepository,
    InMemoryRoomRepository,
)

ROOM_ID = "room-1"
PUZZLE_ID = "puzzle-1"
PLAYER_A = "player-a"
PLAYER_B = "player-b"
TOKEN_A = "token-room-1-player-a"
TOKEN_B = "token-room-1-player-b"


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
                clueId="A1",
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


def make_player(player_id):
    return Player(
        roomId=ROOM_ID,
        playerId=player_id,
        displayName=player_id,
        color="#AABBCC",
        role="player",
    )


@pytest.fixture
def env(monkeypatch):
    room_repository = InMemoryRoomRepository()
    room_repository.create(make_room())

    player_repository = InMemoryPlayerRepository()
    player_repository.add(make_player(PLAYER_A))
    player_repository.add(make_player(PLAYER_B))

    answer_repository = InMemoryAnswerRepository()
    answer_repository.save(
        OfficialAnswers(puzzleId=PUZZLE_ID, answers={"A1": "APPLE"})
    )

    clue_state_repository = InMemoryPlayerClueStateRepository()
    sessions = {
        TOKEN_A: (ROOM_ID, PLAYER_A),
        TOKEN_B: (ROOM_ID, PLAYER_B),
    }

    monkeypatch.setattr(rooms_module, "room_repository", room_repository)
    monkeypatch.setattr(rooms_module, "player_repository", player_repository)
    monkeypatch.setattr(rooms_module, "_sessions", sessions)
    monkeypatch.setattr(gameplay_module, "answer_repository", answer_repository)
    monkeypatch.setattr(
        gameplay_module, "player_clue_state_repository", clue_state_repository
    )
    monkeypatch.setattr(
        drafts_module, "player_clue_state_repository", clue_state_repository
    )

    return SimpleNamespace(
        room_repository=room_repository,
        player_repository=player_repository,
        answer_repository=answer_repository,
        clue_state_repository=clue_state_repository,
    )


@pytest.fixture
def client(env):
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def login_as(client, token):
    client.cookies.set("Session-Token", token)


def test_scenario_valid_player_gets_200_and_official_answer(client):
    login_as(client, TOKEN_A)

    response = client.post(f"/rooms/{ROOM_ID}/clues/A1/reveal")

    assert response.status_code == 200
    assert response.json() == {"answer": "APPLE"}


def test_scenario_successful_request_sets_revealed_strictly_true(client, env):
    login_as(client, TOKEN_A)

    response = client.post(f"/rooms/{ROOM_ID}/clues/A1/reveal")

    assert response.status_code == 200
    state = env.clue_state_repository.get(ROOM_ID, PLAYER_A, "A1")
    assert state is not None
    assert state.revealed is True


def test_scenario_missing_official_answer_returns_400(client):
    login_as(client, TOKEN_A)

    response = client.post(f"/rooms/{ROOM_ID}/clues/D1/reveal")

    assert response.status_code == 400
    assert "detail" in response.json()


def test_scenario_player_a_reveal_does_not_alter_player_b_state(client, env):
    env.clue_state_repository.save(
        PlayerClueState(playerId=PLAYER_B, clueId="A1", revealed=False), ROOM_ID
    )
    login_as(client, TOKEN_A)

    response = client.post(f"/rooms/{ROOM_ID}/clues/A1/reveal")

    assert response.status_code == 200
    state_a = env.clue_state_repository.get(ROOM_ID, PLAYER_A, "A1")
    state_b = env.clue_state_repository.get(ROOM_ID, PLAYER_B, "A1")
    assert state_a.revealed is True
    assert state_b is not None
    assert state_b.revealed is False


def test_edge_repeating_reveal_returns_200_and_answer_again(client, env):
    login_as(client, TOKEN_A)

    first = client.post(f"/rooms/{ROOM_ID}/clues/A1/reveal")
    second = client.post(f"/rooms/{ROOM_ID}/clues/A1/reveal")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == {"answer": "APPLE"}
    assert second.json() == {"answer": "APPLE"}
    state = env.clue_state_repository.get(ROOM_ID, PLAYER_A, "A1")
    assert state.revealed is True
