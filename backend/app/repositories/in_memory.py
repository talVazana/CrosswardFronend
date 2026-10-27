from ..models.admin_solve import AdminSolve
from ..models.answers import OfficialAnswers
from ..models.gameplay import PlayerClueState, ScoreEvent, Submission, SubmissionStatus
from ..models.player_total import PlayerTotal
from ..models.puzzle import Puzzle
from ..models.room import Player, PlayerIdentity, Room
from .interfaces import (
    AdminSolveRepository,
    AnswerRepository,
    PlayerClueStateRepository,
    PlayerIdentityRepository,
    PlayerRepository,
    PlayerTotalRepository,
    PuzzleRepository,
    RoomRepository,
    ScoreRepository,
    SubmissionRepository,
)


class InMemoryRoomRepository(RoomRepository):
    def __init__(self):
        self._rooms: dict[str, Room] = {}

    def create(self, room: Room) -> None:
        self._rooms[room.roomId] = room

    def get(self, room_id: str) -> Room | None:
        return self._rooms.get(room_id)

    def update(self, room: Room) -> None:
        self._rooms[room.roomId] = room

    def list_all(self) -> list[Room]:
        return list(self._rooms.values())


class InMemoryPlayerRepository(PlayerRepository):
    def __init__(self):
        self._players: dict[tuple[str, str], Player] = {}

    def add(self, player: Player) -> None:
        self._players[(player.roomId, player.playerId)] = player

    def get(self, room_id: str, player_id: str) -> Player | None:
        return self._players.get((room_id, player_id))

    def list_by_room(self, room_id: str) -> list[Player]:
        return [p for (rid, _), p in self._players.items() if rid == room_id]


class InMemoryPlayerIdentityRepository(PlayerIdentityRepository):
    def __init__(self) -> None:
        self._identities: dict[str, PlayerIdentity] = {}

    def get(self, name_key: str) -> PlayerIdentity | None:
        return self._identities.get(name_key)

    def save(self, name_key: str, identity: PlayerIdentity) -> None:
        self._identities[name_key] = identity

    def list_all(self) -> list[PlayerIdentity]:
        return list(self._identities.values())


class InMemoryPlayerTotalRepository(PlayerTotalRepository):
    def __init__(self) -> None:
        self._totals: dict[str, PlayerTotal] = {}

    def get(self, name_key: str) -> PlayerTotal | None:
        return self._totals.get(name_key)

    def save(self, name_key: str, total: PlayerTotal) -> None:
        self._totals[name_key] = total

    def list_all(self) -> list[PlayerTotal]:
        return list(self._totals.values())


class InMemoryPuzzleRepository(PuzzleRepository):
    def __init__(self):
        self._puzzles: dict[str, Puzzle] = {}

    def save_snapshot(self, puzzle: Puzzle) -> None:
        self._puzzles[puzzle.puzzleId] = puzzle

    def get_snapshot(self, puzzle_id: str) -> Puzzle | None:
        return self._puzzles.get(puzzle_id)


class InMemoryAnswerRepository(AnswerRepository):
    def __init__(self):
        self._answers: dict[str, OfficialAnswers] = {}

    def save(self, answers: OfficialAnswers) -> None:
        self._answers[answers.puzzleId] = answers

    def get(self, puzzle_id: str) -> OfficialAnswers | None:
        return self._answers.get(puzzle_id)


class InMemorySubmissionRepository(SubmissionRepository):
    def __init__(self):
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

    def list_by_player(self, room_id: str, player_id: str) -> list[Submission]:
        return [
            s
            for s in self._submissions.values()
            if s.roomId == room_id and s.playerId == player_id
        ]

    def update_status(self, submission_id: str, status: SubmissionStatus, points: int) -> None:
        submission = self._submissions.get(submission_id)
        if submission is None:
            return
        submission.status = status
        submission.pointsAwarded = points


class InMemoryPlayerClueStateRepository(PlayerClueStateRepository):
    def __init__(self):
        self.states: dict[tuple[str, str, str], PlayerClueState] = {}

    def save(self, state: PlayerClueState, room_id: str) -> None:
        self.states[(room_id, state.playerId, state.clueId)] = state

    def get(self, room_id: str, player_id: str, clue_id: str) -> PlayerClueState | None:
        return self.states.get((room_id, player_id, clue_id))

    def list_by_player(self, room_id: str, player_id: str) -> list[PlayerClueState]:
        return [
            state
            for (rid, pid, _), state in self.states.items()
            if rid == room_id and pid == player_id
        ]


class InMemoryScoreRepository(ScoreRepository):
    def __init__(self):
        self._events: dict[str, ScoreEvent] = {}

    def add_event(self, event: ScoreEvent) -> None:
        self._events[event.scoreEventId] = event

    def list_by_room(self, room_id: str) -> list[ScoreEvent]:
        return [e for e in self._events.values() if e.roomId == room_id]


class InMemoryAdminSolveRepository(AdminSolveRepository):
    def __init__(self) -> None:
        self._solves: dict[tuple[str, str], AdminSolve] = {}

    def add(self, solve: AdminSolve) -> bool:
        key = (solve.roomId, solve.clueId)
        if key in self._solves:
            return False
        self._solves[key] = solve
        return True

    def list_by_room(self, room_id: str) -> list[AdminSolve]:
        return [s for (rid, _), s in self._solves.items() if rid == room_id]

    def remove_room(self, room_id: str) -> None:
        self._solves = {
            key: solve
            for key, solve in self._solves.items()
            if key[0] != room_id
        }
