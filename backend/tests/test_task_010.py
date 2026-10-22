import pytest

from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Player, Room, RoomStatus
from app.repositories.in_memory import InMemoryPlayerRepository, InMemoryRoomRepository
from app.services.room_service import RoomService


def make_puzzle(puzzle_id: str = "puzzle_A") -> Puzzle:
    return Puzzle(
        puzzleId=puzzle_id,
        title="Secret Puzzle",
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
                text="Secret clue",
                answerLength=1,
            )
        ],
    )


def make_room(room_id: str, title: str) -> Room:
    return Room(
        roomId=room_id,
        title=title,
        status=RoomStatus.lobby,
        puzzleSnapshot=make_puzzle(f"puzzle_{room_id}"),
        creatorId="creator1",
    )


def make_player(room_id: str, player_id: str, display_name: str) -> Player:
    return Player(
        roomId=room_id,
        playerId=player_id,
        displayName=display_name,
        color="#AABBCC",
        role="player",
    )


def build_service() -> RoomService:
    room_repo = InMemoryRoomRepository()
    player_repo = InMemoryPlayerRepository()

    room_repo.create(make_room("room_A", "Room A"))
    room_repo.create(make_room("room_B", "Room B"))

    player_repo.add(make_player("room_A", "player_1", "Alice"))
    player_repo.add(make_player("room_B", "player_2", "Bob"))

    return RoomService(room_repo, player_repo)


def test_verify_player_in_room_returns_true_for_player_in_own_room():
    service = build_service()
    assert service.verify_player_in_room("room_A", "player_1") is True


def test_verify_player_in_room_rejects_player_from_different_room():
    service = build_service()
    assert service.verify_player_in_room("room_B", "player_1") is False


def test_verify_player_in_room_returns_false_for_non_existent_player():
    service = build_service()
    assert service.verify_player_in_room("room_A", "non_existent_player") is False


def test_verify_player_in_room_returns_false_for_missing_room():
    service = build_service()
    assert service.verify_player_in_room("missing_room", "player_1") is False


def test_get_room_public_state_includes_title_and_player_display_name():
    service = build_service()
    state = service.get_room_public_state("room_A")
    assert state["title"] == "Room A"
    assert state["id"] == "room_A"
    assert len(state["players"]) == 1
    assert state["players"][0]["id"] == "player_1"
    assert state["players"][0]["displayName"] == "Alice"


def test_get_room_public_state_omits_puzzle_snapshot():
    service = build_service()
    state = service.get_room_public_state("room_A")
    assert "puzzleSnapshot" not in state
    assert "puzzle_snapshot" not in state


def test_get_room_public_state_omits_official_answers_and_private_drafts():
    service = build_service()
    state = service.get_room_public_state("room_A")
    keys = {key.lower() for key in state}
    assert "officialanswers" not in keys
    assert "answers" not in keys
    assert "drafts" not in keys
    for player in state["players"]:
        player_keys = {key.lower() for key in player}
        assert "draft" not in player_keys
        assert "drafts" not in player_keys
        assert "role" not in player_keys
        assert set(player) == {"id", "displayName", "color"}


def test_get_room_public_state_missing_room_raises_value_error():
    service = build_service()
    with pytest.raises(ValueError) as exc_info:
        service.get_room_public_state("missing_room")
    assert str(exc_info.value) == "Room not found"


def test_get_room_public_state_does_not_leak_other_rooms_players():
    service = build_service()
    state = service.get_room_public_state("room_A")
    player_ids = [player["id"] for player in state["players"]]
    assert "player_2" not in player_ids
