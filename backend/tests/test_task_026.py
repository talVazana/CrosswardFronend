import pytest

import app.services.scoring_service as scoring_service
from app.models.gameplay import ScoreEvent
from app.repositories.interfaces import ScoreRepository
from app.services.scoring_service import ScoringService, apply_score, calculate_points


ROOM_ID = "room-1"
CLUE_ID = "A1"
OTHER_CLUE_ID = "A2"
PLAYER_A = "player-a"
PLAYER_B = "player-b"
ADMIN = "admin-1"


def make_event(player_id, points, clue_id=CLUE_ID, room_id=ROOM_ID, event_id=None):
    return ScoreEvent(
        scoreEventId=event_id or f"score-{player_id}-{points}",
        roomId=room_id,
        playerId=player_id,
        clueId=clue_id,
        points=points,
        reason="correct_submission",
    )


class FakeScoreRepository(ScoreRepository):
    def __init__(self, events=None):
        self.events = list(events or [])
        self.list_calls = 0

    def add_event(self, event):
        self.events.append(event)

    def list_by_room(self, room_id):
        self.list_calls += 1
        return [event for event in self.events if event.roomId == room_id]


class ExplodingScoreRepository(ScoreRepository):
    def add_event(self, event):
        raise AssertionError("repository.add_event should not be called")

    def list_by_room(self, room_id):
        raise AssertionError("repository.list_by_room should not be called")


@pytest.fixture
def service_factory(monkeypatch):
    def build(events=None):
        service = ScoringService(FakeScoreRepository(events))
        monkeypatch.setattr(scoring_service, "_default_service", service)
        return service

    return build


@pytest.fixture
def exploding_service(monkeypatch):
    service = ScoringService(ExplodingScoreRepository())
    monkeypatch.setattr(scoring_service, "_default_service", service)
    return service


def test_public_functions_are_importable():
    assert callable(calculate_points)
    assert callable(apply_score)


def test_given_empty_score_history_when_player_submits_correctly_then_returns_2(service_factory):
    service_factory([])

    points = calculate_points(ROOM_ID, CLUE_ID, PLAYER_A, True, "player")

    assert points == 2


def test_given_player_a_already_scored_when_player_b_submits_correctly_then_returns_1(service_factory):
    service_factory([make_event(PLAYER_A, 2)])

    points = calculate_points(ROOM_ID, CLUE_ID, PLAYER_B, True, "player")

    assert points == 1


def test_given_player_a_already_scored_when_player_a_submits_correctly_again_then_returns_0(service_factory):
    service_factory([make_event(PLAYER_A, 2)])

    points = calculate_points(ROOM_ID, CLUE_ID, PLAYER_A, True, "player")

    assert points == 0


def test_given_player_a_already_scored_when_admin_submits_correctly_then_returns_0(service_factory):
    service_factory([make_event(PLAYER_A, 2)])

    points = calculate_points(ROOM_ID, CLUE_ID, ADMIN, True, "admin")

    assert points == 0


def test_given_previous_scoring_on_other_clue_when_player_submits_then_returns_2(service_factory):
    service_factory([make_event(PLAYER_A, 2, clue_id=OTHER_CLUE_ID)])

    points = calculate_points(ROOM_ID, CLUE_ID, PLAYER_B, True, "player")

    assert points == 2


def test_given_first_apply_score_with_points_2_and_red_then_state_solved_and_red(service_factory):
    service = service_factory([])

    event = apply_score(ROOM_ID, CLUE_ID, PLAYER_A, 2, "#FF0000")
    state = service.get_public_clue_state(ROOM_ID, CLUE_ID)

    assert event.points == 2
    assert state.solved is True
    assert state.firstSolverColor == "#FF0000"


def test_given_subsequent_apply_score_with_points_1_and_green_then_first_solver_color_remains_red(service_factory):
    service = service_factory([])
    apply_score(ROOM_ID, CLUE_ID, PLAYER_A, 2, "#FF0000")

    apply_score(ROOM_ID, CLUE_ID, PLAYER_B, 1, "#00FF00")
    state = service.get_public_clue_state(ROOM_ID, CLUE_ID)

    assert state.solved is True
    assert state.firstSolverColor == "#FF0000"


def test_apply_score_records_event_and_subsequent_calculate_points_returns_1(service_factory):
    service = service_factory([])
    apply_score(ROOM_ID, CLUE_ID, PLAYER_A, 2, "#FF0000")

    points = calculate_points(ROOM_ID, CLUE_ID, PLAYER_B, True, "player")

    assert points == 1
    assert len(service._score_repository.events) == 1


def test_negative_points_are_never_returned(service_factory):
    scenarios = [
        ([], PLAYER_A, True, "player"),
        ([make_event(PLAYER_A, 2)], PLAYER_B, True, "player"),
        ([make_event(PLAYER_A, 2)], PLAYER_A, True, "player"),
        ([], ADMIN, True, "admin"),
        ([], PLAYER_A, False, "player"),
    ]

    for events, player_id, is_correct, role in scenarios:
        service_factory(events)
        points = calculate_points(ROOM_ID, CLUE_ID, player_id, is_correct, role)
        assert points >= 0, (player_id, is_correct, role, points)


def test_incorrect_submission_returns_0_without_querying_repository(exploding_service):
    points = calculate_points(ROOM_ID, CLUE_ID, PLAYER_A, False, "player")

    assert points == 0


def test_admin_submission_returns_0_without_querying_repository(exploding_service):
    points = calculate_points(ROOM_ID, CLUE_ID, ADMIN, True, "admin")

    assert points == 0
