import abc

import pytest

from app.models.answers import OfficialAnswers
from app.models.gameplay import ScoreEvent, Submission, SubmissionStatus
from app.models.puzzle import Cell, Clue, Puzzle
from app.models.room import Player, Room, RoomStatus
from app.repositories import interfaces
from app.repositories.in_memory import (
    InMemoryAnswerRepository,
    InMemoryPlayerRepository,
    InMemoryPuzzleRepository,
    InMemoryRoomRepository,
    InMemoryScoreRepository,
    InMemorySubmissionRepository,
)


def make_puzzle(puzzle_id: str = "puzzle1") -> Puzzle:
    return Puzzle(
        puzzleId=puzzle_id,
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
                clueId="clue1",
                number=1,
                direction="across",
                text="Test clue",
                answerLength=1,
            )
        ],
    )


def make_room(room_id: str = "room1", title: str = "Room One") -> Room:
    return Room(
        roomId=room_id,
        title=title,
        status=RoomStatus.draft,
        puzzleSnapshot=make_puzzle(),
        creatorId="creator1",
    )


def make_player(room_id: str = "room1", player_id: str = "playerA_id") -> Player:
    return Player(
        roomId=room_id,
        playerId=player_id,
        displayName=player_id,
        color="#AABBCC",
        role="player",
    )


def make_submission(
    submission_id: str = "sub1",
    room_id: str = "room1",
    status: SubmissionStatus = SubmissionStatus.pending,
) -> Submission:
    return Submission(
        submissionId=submission_id,
        roomId=room_id,
        playerId="playerA_id",
        clueId="clue1",
        answer="A",
        status=status,
    )


def make_score_event(
    event_id: str = "event1", room_id: str = "room1"
) -> ScoreEvent:
    return ScoreEvent(
        scoreEventId=event_id,
        roomId=room_id,
        playerId="playerA_id",
        clueId="clue1",
        points=10,
        reason="correct",
    )


def test_room_save_then_get_returns_identical_object():
    repo = InMemoryRoomRepository()
    room = make_room()
    repo.create(room)
    assert repo.get("room1") is room


def test_room_get_non_existent_returns_none_without_exception():
    repo = InMemoryRoomRepository()
    assert repo.get("non_existent") is None


def test_room_get_invalid_id_returns_none():
    assert InMemoryRoomRepository().get("invalid_id") is None


def test_room_update_changes_fields():
    repo = InMemoryRoomRepository()
    repo.create(make_room(title="Original"))
    updated = make_room(title="Updated")
    updated.status = RoomStatus.active
    repo.update(updated)
    stored = repo.get("room1")
    assert stored is not None
    assert stored.title == "Updated"
    assert stored.status == RoomStatus.active


def test_room_update_does_not_overwrite_unrelated_rooms():
    repo = InMemoryRoomRepository()
    repo.create(make_room("room1", "One"))
    repo.create(make_room("room2", "Two"))
    repo.update(make_room("room1", "One Updated"))
    assert repo.get("room1").title == "One Updated"
    assert repo.get("room2").title == "Two"


def test_player_list_by_room_returns_only_that_room():
    repo = InMemoryPlayerRepository()
    player_a = make_player("room1", "playerA_id")
    player_b = make_player("room2", "playerB_id")
    repo.add(player_a)
    repo.add(player_b)
    result = repo.list_by_room("room1")
    assert result == [player_a]
    assert len(result) == 1


def test_player_get_with_wrong_room_returns_none():
    repo = InMemoryPlayerRepository()
    repo.add(make_player("room1", "playerA_id"))
    assert repo.get("room2", "playerA_id") is None


def test_player_get_existing_returns_player():
    repo = InMemoryPlayerRepository()
    player = make_player("room1", "player1")
    repo.add(player)
    assert repo.get("room1", "player1") is player


def test_player_get_missing_returns_none():
    repo = InMemoryPlayerRepository()
    assert repo.get("room1", "missing") is None


def test_player_list_by_room_with_no_players_returns_empty_list():
    assert InMemoryPlayerRepository().list_by_room("room1") == []


def test_puzzle_save_and_get_snapshot():
    repo = InMemoryPuzzleRepository()
    puzzle = make_puzzle()
    repo.save_snapshot(puzzle)
    assert repo.get_snapshot("puzzle1") is puzzle
    assert repo.get_snapshot("missing") is None


def test_answer_save_and_get():
    repo = InMemoryAnswerRepository()
    answers = OfficialAnswers(puzzleId="puzzle1", answers={"clue1": "A"})
    repo.save(answers)
    assert repo.get("puzzle1") is answers
    assert repo.get("missing") is None


def test_submission_add_and_get():
    repo = InMemorySubmissionRepository()
    submission = make_submission()
    repo.add(submission)
    assert repo.get("sub1") is submission
    assert repo.get("missing") is None


def test_submission_list_by_room_with_zero_submissions_returns_empty_list():
    assert InMemorySubmissionRepository().list_pending_by_room("room1") == []


def test_submission_list_pending_by_room_filters_room_and_status():
    repo = InMemorySubmissionRepository()
    pending_room1 = make_submission("sub1", "room1", SubmissionStatus.pending)
    pending_room2 = make_submission("sub2", "room2", SubmissionStatus.pending)
    correct_room1 = make_submission("sub3", "room1", SubmissionStatus.correct)
    repo.add(pending_room1)
    repo.add(pending_room2)
    repo.add(correct_room1)
    assert repo.list_pending_by_room("room1") == [pending_room1]


def test_submission_update_status_changes_entry_and_leaves_others():
    repo = InMemorySubmissionRepository()
    target = make_submission("sub1")
    other = make_submission("sub2")
    repo.add(target)
    repo.add(other)
    repo.update_status("sub1", SubmissionStatus.correct, 5)
    assert repo.get("sub1").status == SubmissionStatus.correct
    assert repo.get("sub1").pointsAwarded == 5
    assert repo.get("sub2").status == SubmissionStatus.pending
    assert repo.get("sub2").pointsAwarded == 0


def test_submission_update_status_missing_id_does_not_raise():
    repo = InMemorySubmissionRepository()
    repo.update_status("missing", SubmissionStatus.correct, 5)


def test_score_add_event_and_list_by_room():
    repo = InMemoryScoreRepository()
    event_room1 = make_score_event("event1", "room1")
    event_room2 = make_score_event("event2", "room2")
    repo.add_event(event_room1)
    repo.add_event(event_room2)
    assert repo.list_by_room("room1") == [event_room1]
    assert repo.list_by_room("empty_room") == []


CONCRETE_REPOSITORIES = [
    (InMemoryRoomRepository, interfaces.RoomRepository),
    (InMemoryPlayerRepository, interfaces.PlayerRepository),
    (InMemoryPuzzleRepository, interfaces.PuzzleRepository),
    (InMemoryAnswerRepository, interfaces.AnswerRepository),
    (InMemorySubmissionRepository, interfaces.SubmissionRepository),
    (InMemoryScoreRepository, interfaces.ScoreRepository),
]


@pytest.mark.parametrize("concrete_cls, abstract_cls", CONCRETE_REPOSITORIES)
def test_in_memory_classes_satisfy_abc_requirements(concrete_cls, abstract_cls):
    assert issubclass(concrete_cls, abstract_cls)
    assert issubclass(concrete_cls, abc.ABC)
    assert concrete_cls.__abstractmethods__ == frozenset()
    assert isinstance(concrete_cls(), abstract_cls)
