from types import SimpleNamespace

import pytest

from app.api.routes import admin as admin_module
from app.api.routes import rooms as rooms_module
from app.models.admin_solve import AdminSolve
from app.models.gameplay import ScoreEvent, utc_now
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Player, Room, RoomStatus
from app.repositories.in_memory import InMemoryRoomRepository
from app.services import admin_solves, scoring_service, telegram_notifier

ROOM_ID = "telegram-room"


def make_puzzle() -> Puzzle:
    return Puzzle(
        puzzleId="puzzle_telegram",
        title="Telegram puzzle",
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
                text="Clue",
                answerLength=1,
            )
        ],
    )


def make_room(status: RoomStatus = RoomStatus.lobby) -> Room:
    return Room(
        roomId=ROOM_ID,
        title="Friday night crossword",
        status=status,
        puzzleSnapshot=make_puzzle(),
        creatorId="creator1",
    )


def add_player(name: str, player_id: str) -> Player:
    player = Player(
        roomId=ROOM_ID,
        playerId=player_id,
        displayName=name,
        color="#DC2626",
        role="player",
    )
    rooms_module.player_repository.add(player)
    return player


def add_score(player_id: str, points: int, clue_id: str) -> None:
    scoring_service._default_service._score_repository.add_event(
        ScoreEvent(
            scoreEventId=f"score-{player_id}-{clue_id}",
            roomId=ROOM_ID,
            playerId=player_id,
            clueId=clue_id,
            points=points,
            reason="correct_submission",
            timestamp=utc_now(),
        )
    )


@pytest.fixture
def room_state():
    rooms_module.room_repository = InMemoryRoomRepository()
    rooms_module.room_repository.create(make_room())
    rooms_module.player_repository._players = {}
    scoring_service._default_service._score_repository._events = {}
    scoring_service._default_service._public_clue_states.clear()
    return rooms_module.room_repository.get(ROOM_ID)


def test_started_message_has_title_room_and_player_count(room_state):
    add_player("Dana", "player-1")
    add_player("Amit", "player-2")

    message = telegram_notifier.format_started_message(room_state)

    assert "Friday night crossword" in message
    assert ROOM_ID in message
    assert "Players: 2" in message


def test_finished_message_has_winner_and_score_guide(room_state):
    add_player("Dana", "player-1")
    add_player("Amit", "player-2")
    add_score("player-1", 2, "clue1")
    add_score("player-1", 1, "clue2")
    add_score("player-2", 2, "clue3")
    admin_solves.repository.add(
        AdminSolve(
            roomId=ROOM_ID,
            clueId="clue4",
            adminId="admin-1",
            solvedAt=utc_now(),
        )
    )

    message = telegram_notifier.format_finished_message(room_state)

    assert "Game finished: Friday night crossword" in message
    assert "Winner: Dana (3 pts)" in message
    assert "Admin vs players (clues): 1 - 2" in message


def test_finished_message_without_points_reports_no_winner(room_state):
    add_player("Dana", "player-1")

    message = telegram_notifier.format_finished_message(room_state)

    assert "Winner: No winner (no points)" in message
    assert "Admin vs players (clues): 0 - 0" in message


def test_notifier_is_disabled_without_configuration(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    assert telegram_notifier.is_enabled() is False


def test_notifier_is_disabled_during_tests_by_default(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.delenv("TELEGRAM_ALLOW_IN_TESTS", raising=False)

    assert telegram_notifier.is_enabled() is False


def test_disabled_notifier_does_not_send(room_state, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    def fail(_text):
        raise AssertionError("send must not be called when disabled")

    monkeypatch.setattr(telegram_notifier, "_send_message", fail)

    telegram_notifier.notify_game_started(room_state)
    telegram_notifier.notify_game_finished(room_state)


def test_start_transition_sends_started_notification(room_state, monkeypatch):
    sent = []
    monkeypatch.setattr(
        telegram_notifier, "notify_game_started", lambda room: sent.append("start")
    )
    monkeypatch.setattr(
        telegram_notifier, "notify_game_finished", lambda room: sent.append("finish")
    )
    monkeypatch.setattr(admin_module, "_resolve_admin", lambda request: SimpleNamespace())

    admin_module._admin_transition(ROOM_ID, "start", SimpleNamespace())

    assert sent == ["start"]


def test_finish_transition_sends_finished_notification(monkeypatch):
    rooms_module.room_repository = InMemoryRoomRepository()
    rooms_module.room_repository.create(make_room(RoomStatus.active))

    sent = []
    monkeypatch.setattr(
        telegram_notifier, "notify_game_started", lambda room: sent.append("start")
    )
    monkeypatch.setattr(
        telegram_notifier, "notify_game_finished", lambda room: sent.append("finish")
    )
    monkeypatch.setattr(admin_module, "_resolve_admin", lambda request: SimpleNamespace())

    admin_module._admin_transition(ROOM_ID, "finish", SimpleNamespace())

    assert sent == ["finish"]
