import pytest
from fastapi.testclient import TestClient

from app.api.routes import scores as scores_module
from app.main import app
from app.models.gameplay import ScoreEvent
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Player, Room, RoomStatus
from app.repositories.in_memory import (
    InMemoryPlayerRepository,
    InMemoryRoomRepository,
    InMemoryScoreRepository,
)

ROOM_ID = "room-047"


def make_puzzle() -> Puzzle:
    return Puzzle(
        puzzleId="puzzle-047",
        title="Task 047 Puzzle",
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
                text="Test clue",
                answerLength=5,
            )
        ],
    )


def make_room(room_id: str = ROOM_ID) -> Room:
    return Room(
        roomId=room_id,
        title="Task 047 Room",
        status=RoomStatus.active,
        puzzleSnapshot=make_puzzle(),
        creatorId="admin-047",
    )


def make_player(
    player_id: str, display_name: str, room_id: str = ROOM_ID
) -> Player:
    return Player(
        roomId=room_id,
        playerId=player_id,
        displayName=display_name,
        color="#112233",
        role="player",
    )


_event_counter = 0


def make_event(player_id: str, points: int, room_id: str = ROOM_ID) -> ScoreEvent:
    global _event_counter
    _event_counter += 1
    return ScoreEvent(
        scoreEventId=f"event-{_event_counter}",
        roomId=room_id,
        playerId=player_id,
        clueId="A1",
        points=points,
        reason="clue solved",
    )


@pytest.fixture
def repositories(monkeypatch):
    room_repo = InMemoryRoomRepository()
    player_repo = InMemoryPlayerRepository()
    score_repo = InMemoryScoreRepository()
    monkeypatch.setattr(scores_module, "room_repository", room_repo)
    monkeypatch.setattr(scores_module, "player_repository", player_repo)
    monkeypatch.setattr(scores_module, "score_repository", score_repo)
    return room_repo, player_repo, score_repo


@pytest.fixture
def client():
    return TestClient(app)


def seed(
    repositories,
    room_id: str = ROOM_ID,
    room: bool = True,
):
    room_repo, player_repo, score_repo = repositories
    if room:
        room_repo.create(make_room(room_id))
    return room_repo, player_repo, score_repo


def totals_by_player(payload):
    return {entry["playerId"]: entry["totalPoints"] for entry in payload}


def test_dana_two_points_amir_one_point(repositories, client):
    _, player_repo, score_repo = seed(repositories)
    player_repo.add(make_player("dana", "Dana"))
    player_repo.add(make_player("amir", "Amir"))
    score_repo.add_event(make_event("dana", 1))
    score_repo.add_event(make_event("dana", 1))
    score_repo.add_event(make_event("amir", 1))

    response = client.get(f"/rooms/{ROOM_ID}/scores")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 2, payload
    assert totals_by_player(payload) == {"dana": 2, "amir": 1}
    for entry in payload:
        assert set(entry) == {"playerId", "displayName", "color", "totalPoints"}, entry
        assert isinstance(entry["totalPoints"], int), entry


def test_player_with_no_score_events_has_zero_total(repositories, client):
    _, player_repo, score_repo = seed(repositories)
    player_repo.add(make_player("lee", "Lee"))
    player_repo.add(make_player("dana", "Dana"))
    score_repo.add_event(make_event("dana", 2))

    response = client.get(f"/rooms/{ROOM_ID}/scores")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert totals_by_player(payload) == {"lee": 0, "dana": 2}, payload
    lee = next(entry for entry in payload if entry["playerId"] == "lee")
    assert lee["totalPoints"] == 0


def test_equal_totals_ordered_by_display_name_ascending(repositories, client):
    _, player_repo, score_repo = seed(repositories)
    player_repo.add(make_player("zoe", "Zoe"))
    player_repo.add(make_player("amy", "Amy"))
    score_repo.add_event(make_event("zoe", 1))
    score_repo.add_event(make_event("amy", 1))

    response = client.get(f"/rooms/{ROOM_ID}/scores")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [entry["displayName"] for entry in payload] == ["Amy", "Zoe"], payload


def test_different_totals_sorted_descending(repositories, client):
    _, player_repo, score_repo = seed(repositories)
    player_repo.add(make_player("lee", "Lee"))
    player_repo.add(make_player("dana", "Dana"))
    player_repo.add(make_player("amir", "Amir"))
    score_repo.add_event(make_event("dana", 3))
    score_repo.add_event(make_event("amir", 1))

    response = client.get(f"/rooms/{ROOM_ID}/scores")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [entry["playerId"] for entry in payload] == ["dana", "amir", "lee"], payload
    assert [entry["totalPoints"] for entry in payload] == [3, 1, 0], payload


def test_missing_room_returns_404_room_not_found(repositories, client):
    seed(repositories, room=False)

    response = client.get(f"/rooms/{ROOM_ID}/scores")

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Room not found"}, response.text


def test_room_with_no_players_returns_empty_array(repositories, client):
    seed(repositories)

    response = client.get(f"/rooms/{ROOM_ID}/scores")

    assert response.status_code == 200, response.text
    assert response.json() == [], response.text


def test_response_contains_no_secret_keys(repositories, client):
    _, player_repo, score_repo = seed(repositories)
    player_repo.add(make_player("dana", "Dana"))
    score_repo.add_event(make_event("dana", 2))

    response = client.get(f"/rooms/{ROOM_ID}/scores")

    assert response.status_code == 200, response.text
    payload = response.json()
    forbidden = {"answer", "draft", "session-token", "sessiontoken"}

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                assert key.lower() not in forbidden, f"forbidden key: {key}"
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
