from abc import ABC, abstractmethod

from ..models.admin_solve import AdminSolve
from ..models.answers import OfficialAnswers
from ..models.gameplay import PlayerClueState, ScoreEvent, Submission, SubmissionStatus
from ..models.player_total import PlayerTotal
from ..models.puzzle import Puzzle
from ..models.room import Player, PlayerIdentity, Room


class RoomRepository(ABC):
    @abstractmethod
    def create(self, room: Room) -> None: ...

    @abstractmethod
    def get(self, room_id: str) -> Room | None: ...

    @abstractmethod
    def update(self, room: Room) -> None: ...

    @abstractmethod
    def list_all(self) -> list[Room]: ...


class PlayerRepository(ABC):
    @abstractmethod
    def add(self, player: Player) -> None: ...

    @abstractmethod
    def get(self, room_id: str, player_id: str) -> Player | None: ...

    @abstractmethod
    def list_by_room(self, room_id: str) -> list[Player]: ...


class PlayerIdentityRepository(ABC):
    @abstractmethod
    def get(self, name_key: str) -> PlayerIdentity | None: ...

    @abstractmethod
    def save(self, name_key: str, identity: PlayerIdentity) -> None: ...

    @abstractmethod
    def list_all(self) -> list[PlayerIdentity]: ...


class PlayerTotalRepository(ABC):
    @abstractmethod
    def get(self, name_key: str) -> PlayerTotal | None: ...

    @abstractmethod
    def save(self, name_key: str, total: PlayerTotal) -> None: ...

    @abstractmethod
    def list_all(self) -> list[PlayerTotal]: ...


class PuzzleRepository(ABC):
    @abstractmethod
    def save_snapshot(self, puzzle: Puzzle) -> None: ...

    @abstractmethod
    def get_snapshot(self, puzzle_id: str) -> Puzzle | None: ...


class AnswerRepository(ABC):
    @abstractmethod
    def save(self, answers: OfficialAnswers) -> None: ...

    @abstractmethod
    def get(self, puzzle_id: str) -> OfficialAnswers | None: ...


class SubmissionRepository(ABC):
    @abstractmethod
    def add(self, submission: Submission) -> None: ...

    @abstractmethod
    def get(self, submission_id: str) -> Submission | None: ...

    @abstractmethod
    def list_pending_by_room(self, room_id: str) -> list[Submission]: ...

    @abstractmethod
    def list_by_player(self, room_id: str, player_id: str) -> list[Submission]: ...

    @abstractmethod
    def update_status(self, submission_id: str, status: SubmissionStatus, points: int) -> None: ...


class PlayerClueStateRepository(ABC):
    @abstractmethod
    def save(self, state: PlayerClueState, room_id: str) -> None: ...

    @abstractmethod
    def get(self, room_id: str, player_id: str, clue_id: str) -> PlayerClueState | None: ...

    @abstractmethod
    def list_by_player(self, room_id: str, player_id: str) -> list[PlayerClueState]: ...


class ScoreRepository(ABC):
    @abstractmethod
    def add_event(self, event: ScoreEvent) -> None: ...

    @abstractmethod
    def list_by_room(self, room_id: str) -> list[ScoreEvent]: ...


class AdminSolveRepository(ABC):
    @abstractmethod
    def add(self, solve: AdminSolve) -> bool: ...

    @abstractmethod
    def list_by_room(self, room_id: str) -> list[AdminSolve]: ...

    @abstractmethod
    def remove_room(self, room_id: str) -> None: ...
