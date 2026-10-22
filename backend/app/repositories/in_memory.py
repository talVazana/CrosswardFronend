from ..models.answers import OfficialAnswers
from ..models.gameplay import ScoreEvent, Submission, SubmissionStatus
from ..models.puzzle import Puzzle
from ..models.room import Player, Room
from .interfaces import (
    AnswerRepository,
    PlayerRepository,
    PuzzleRepository,
    RoomRepository,
    ScoreRepository,
    SubmissionRepository,
)


class InMemoryRoomRepository(RoomRepository):
    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}

    def create(self, room: Room) -> None:
        self._rooms[room.roomId] = room

    def get(self, room_id: str) -> Room | None:
        return self._rooms.get(room_id)

    def update(self, room: Room) -> None:
        self._rooms[room.roomId] = room


class InMemoryPlayerRepository(PlayerRepository):
    def __init__(self) -> None:
        self._players: dict[tuple[str, str], Player] = {}

    def add(self, player: Player) -> None:
        self._players[(player.roomId, player.playerId)] = player

    def get(self, room_id: str, player_id: str) -> Player | None:
        return self._players.get((room_id, player_id))

    def list_by_room(self, room_id: str) -> list[Player]:
        return [p for (rid, _), p in self._players.items() if rid == room_id]


class InMemoryPuzzleRepository(PuzzleRepository):
    def __init__(self) -> None:
        self._snapshots: dict[str, Puzzle] = {}

    def save_snapshot(self, puzzle: Puzzle) -> None:
        self._snapshots[puzzle.puzzleId] = puzzle

    def get_snapshot(self, puzzle_id: str) -> Puzzle | None:
        return self._snapshots.get(puzzle_id)


class InMemoryAnswerRepository(AnswerRepository):
    def __init__(self) -> None:
        self._answers: dict[str, OfficialAnswers] = {}

    def save(self, answers: OfficialAnswers) -> None:
        self._answers[answers.puzzleId] = answers

    def get(self, puzzle_id: str) -> OfficialAnswers | None:
        return self._answers.get(puzzle_id)


class InMemorySubmissionRepository(SubmissionRepository):
    def __init__(self) -> None:
        self._submissions: dict[str, Submission] = {}

    def add(self, submission: Submission) -> None:
        self._submissions[submission.submissionId] = submission

    def get(self, submission_id: str) -> Submission | None:
        return self._submissions.get(submission_id)

    def list_pending_by_room(self, room_id: str) -> list[Submission]:
        return [
            s
            for s in self._submissions.values()
            if s.roomId == room_id and s.status == SubmissionStatus.pending
        ]

    def update_status(self, submission_id: str, status: SubmissionStatus, points: int) -> None:
        submission = self._submissions.get(submission_id)
        if submission is None:
            return
        submission.status = status
        submission.pointsAwarded = points
        self._submissions[submission_id] = submission


class InMemoryScoreRepository(ScoreRepository):
    def __init__(self) -> None:
        self._events: dict[str, ScoreEvent] = {}

    def add_event(self, event: ScoreEvent) -> None:
        self._events[event.scoreEventId] = event

    def list_by_room(self, room_id: str) -> list[ScoreEvent]:
        return [e for e in self._events.values() if e.roomId == room_id]
