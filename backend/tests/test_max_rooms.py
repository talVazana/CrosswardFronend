import io
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.routes import admin as admin_module
from app.api.routes import drafts as drafts_module
from app.api.routes import rooms as rooms_module
from app.api.routes import submissions as submissions_module
from app.main import app
from app.models.gameplay import ScoreEvent, utc_now
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Player, Room, RoomStatus
from app.repositories.in_memory import (
    InMemoryPlayerClueStateRepository,
    InMemoryPlayerRepository,
    InMemoryPlayerTotalRepository,
    InMemoryRoomRepository,
    InMemoryScoreRepository,
    InMemorySubmissionRepository,
)
from app.services import player_totals
from app.services import scoring_service
from app.services.scoring_service import ScoringService


def make_puzzle(puzzle_id: str = "puzzle-1") -> Puzzle:
    return Puzzle(
        puzzleId=puzzle_id,
        title="Test",
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
                text="Clue",
                answerLength=1,
            )
        ],
    )


def make_room(room_id: str, created_at) -> Room:
    return Room(
        roomId=room_id,
        title=f"Room {room_id}",
        status=RoomStatus.lobby,
        puzzleSnapshot=make_puzzle(f"puzzle-{room_id}"),
        creatorId="admin",
        createdAt=created_at,
    )


@pytest.fixture
def isolated_state(monkeypatch):
    room_repo = InMemoryRoomRepository()
    player_repo = InMemoryPlayerRepository()
    score_repo = InMemoryScoreRepository()
    monkeypatch.setattr(rooms_module, "room_repository", room_repo)
    monkeypatch.setattr(rooms_module, "player_repository", player_repo)
    monkeypatch.setattr(rooms_module, "_sessions", {})
    monkeypatch.setattr(
        scoring_service, "_default_service", ScoringService(score_repo)
    )
    monkeypatch.setattr(
        drafts_module,
        "player_clue_state_repository",
        InMemoryPlayerClueStateRepository(),
    )
    monkeypatch.setattr(
        submissions_module, "submission_repository", InMemorySubmissionRepository()
    )
    monkeypatch.setattr(player_totals, "repository", InMemoryPlayerTotalRepository())
    return room_repo, player_repo, score_repo


def test_create_room_evicts_oldest_when_at_limit(monkeypatch, isolated_state):
    room_repo, _, _ = isolated_state

    base = utc_now()
    for i in range(20):
        room_repo.create(make_room(f"room-{i}", base + timedelta(seconds=i)))

    monkeypatch.setattr(admin_module, "process_image", lambda image_bytes: make_puzzle())
    monkeypatch.setattr(
        admin_module,
        "_resolve_admin",
        lambda request: SimpleNamespace(
            playerId="admin", displayName="a", role="admin"
        ),
    )
    monkeypatch.setattr(
        admin_module.firestore_publisher, "publish_room_image", lambda *a, **k: None
    )

    image = io.BytesIO()
    Image.new("RGB", (4, 4), (1, 2, 3)).save(image, format="JPEG")

    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/admin/rooms",
            content=image.getvalue(),
            headers={"Content-Type": "application/octet-stream"},
            params={"title": "New"},
        )

    assert response.status_code == 201, response.text
    room_ids = {room.roomId for room in room_repo.list_all()}
    assert "room-0" not in room_ids
    assert len(room_ids) == 20
    assert response.json()["roomId"] in room_ids


def test_rebuild_totals_drops_points_from_removed_room(monkeypatch, isolated_state):
    room_repo, player_repo, score_repo = isolated_state

    room_repo.create(make_room("room-a", utc_now()))
    room_repo.create(make_room("room-b", utc_now() + timedelta(seconds=1)))
    player_repo.add(
        Player(roomId="room-a", playerId="p1", displayName="Dana", color="#DC2626", role="player")
    )
    player_repo.add(
        Player(roomId="room-b", playerId="p2", displayName="Dana", color="#DC2626", role="player")
    )

    score_repo.add_event(
        ScoreEvent(
            scoreEventId="e1",
            roomId="room-a",
            playerId="p1",
            clueId="A1",
            points=5,
            reason="correct_submission",
        )
    )
    score_repo.add_event(
        ScoreEvent(
            scoreEventId="e2",
            roomId="room-b",
            playerId="p2",
            clueId="A1",
            points=3,
            reason="correct_submission",
        )
    )

    player_totals.rebuild()
    assert player_totals.get_total("Dana") == 8

    # Remove room-a and rebuild: only room-b's 3 points remain.
    admin_module._remove_room_fully("room-a")
    assert player_totals.get_total("Dana") == 3
