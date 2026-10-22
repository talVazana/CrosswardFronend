from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.models.gameplay import (
    PlayerClueState,
    PublicClueState,
    ScoreEvent,
    Submission,
    SubmissionStatus,
)
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Player, Room, RoomStatus


def make_puzzle():
    return Puzzle(
        puzzleId="puzzle-1",
        title="Test Puzzle",
        width=3,
        height=3,
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
                text="First across entry",
                answerLength=5,
            )
        ],
    )


def make_room(**overrides):
    data = {
        "roomId": "room-1",
        "title": "Test Room",
        "status": RoomStatus.lobby,
        "puzzleSnapshot": make_puzzle(),
        "creatorId": "user-1",
    }
    data.update(overrides)
    return data


def make_player(**overrides):
    data = {
        "roomId": "room-1",
        "playerId": "player-1",
        "displayName": "Alice",
        "color": "#123456",
        "role": "player",
    }
    data.update(overrides)
    return data


def make_submission(**overrides):
    data = {
        "submissionId": "sub-1",
        "roomId": "room-1",
        "playerId": "player-1",
        "clueId": "A1",
        "answer": "HELLO",
    }
    data.update(overrides)
    return data


def make_score_event(**overrides):
    data = {
        "scoreEventId": "score-1",
        "roomId": "room-1",
        "playerId": "player-1",
        "clueId": "A1",
        "points": 10,
        "reason": "correct answer",
    }
    data.update(overrides)
    return data


def assert_timezone_aware_utc(value):
    assert isinstance(value, datetime)
    assert value.tzinfo is not None
    assert value.utcoffset() == timedelta(0)
    assert value.tzinfo == timezone.utc


def test_room_lobby_defaults_created_at_and_updated_at_to_aware_utc():
    room = Room(**make_room())

    assert room.status is RoomStatus.lobby
    assert_timezone_aware_utc(room.createdAt)
    assert_timezone_aware_utc(room.updatedAt)


def test_room_rejects_unknown_status_string():
    with pytest.raises(ValidationError):
        Room(**make_room(status="unknown_status"))


def test_player_valid_hex_color_is_accepted():
    player = Player(**make_player(color="#123456"))

    assert player.color == "#123456"


def test_player_rejects_malformed_colors():
    with pytest.raises(ValidationError):
        Player(**make_player(color="not-a-color"))
    with pytest.raises(ValidationError):
        Player(**make_player(color="FF5733"))


def test_player_rejects_moderator_role():
    with pytest.raises(ValidationError):
        Player(**make_player(role="moderator"))


def test_submission_defaults_status_pending_and_points_zero():
    submission = Submission(**make_submission())

    assert submission.status is SubmissionStatus.pending
    assert submission.pointsAwarded == 0
    assert_timezone_aware_utc(submission.serverTimestamp)


def test_submission_and_score_event_reject_negative_points():
    with pytest.raises(ValidationError):
        Submission(**make_submission(pointsAwarded=-1))
    with pytest.raises(ValidationError):
        ScoreEvent(**make_score_event(points=-5))


def test_player_clue_state_revealed_true_scored_false():
    state = PlayerClueState(
        playerId="player-1", clueId="A1", revealed=True, scored=False
    )

    assert state.revealed is True
    assert state.scored is False
    assert state.draft == ""


def test_public_clue_state_preserves_first_solver_color():
    state = PublicClueState(clueId="A1", solved=True, firstSolverColor="#00FF00")

    assert state.solved is True
    assert state.firstSolverColor == "#00FF00"


def test_color_without_hash_prefix_raises_validation_error():
    with pytest.raises(ValidationError):
        Player(**make_player(color="FF5733"))


def test_role_outside_player_admin_raises_validation_error():
    with pytest.raises(ValidationError):
        Player(**make_player(role="spectator"))


def test_zero_points_are_accepted_for_submission_and_score_event():
    submission = Submission(**make_submission(pointsAwarded=0))
    event = ScoreEvent(**make_score_event(points=0))

    assert submission.pointsAwarded == 0
    assert event.points == 0


def test_room_status_has_all_required_members():
    assert RoomStatus("draft") is RoomStatus.draft
    assert RoomStatus("lobby") is RoomStatus.lobby
    assert RoomStatus("active") is RoomStatus.active
    assert RoomStatus("paused") is RoomStatus.paused
    assert RoomStatus("finished") is RoomStatus.finished
    assert RoomStatus("closed") is RoomStatus.closed


def test_submission_status_has_all_required_members():
    assert SubmissionStatus("pending") is SubmissionStatus.pending
    assert SubmissionStatus("correct") is SubmissionStatus.correct
    assert SubmissionStatus("incorrect") is SubmissionStatus.incorrect


def test_submission_rejects_unknown_status_string():
    with pytest.raises(ValidationError):
        Submission(**make_submission(status="unknown_status"))


def test_player_defaults_joined_at_to_aware_utc():
    player = Player(**make_player())

    assert_timezone_aware_utc(player.joinedAt)


def test_score_event_defaults_timestamp_to_aware_utc():
    event = ScoreEvent(**make_score_event())

    assert_timezone_aware_utc(event.timestamp)
