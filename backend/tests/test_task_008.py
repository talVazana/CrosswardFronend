import inspect
import typing

import pytest

from app.models.answers import OfficialAnswers
from app.models.gameplay import ScoreEvent, Submission, SubmissionStatus
from app.models.puzzle import Puzzle
from app.models.room import Player, Room
from app.repositories import interfaces
from app.repositories.interfaces import (
    AnswerRepository,
    PlayerRepository,
    PuzzleRepository,
    RoomRepository,
    ScoreRepository,
    SubmissionRepository,
)

ALL_REPOSITORIES = [
    RoomRepository,
    PlayerRepository,
    PuzzleRepository,
    AnswerRepository,
    SubmissionRepository,
    ScoreRepository,
]


def test_room_repository_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        RoomRepository()


def test_dummy_player_repository_missing_list_by_room_raises_type_error():
    class DummyPlayerRepo(PlayerRepository):
        def add(self, player: Player) -> None:
            pass

        def get(self, room_id: str, player_id: str) -> Player | None:
            return None

    with pytest.raises(TypeError):
        DummyPlayerRepo()


@pytest.mark.parametrize("repo_cls", ALL_REPOSITORIES)
def test_all_repositories_are_uninstantiable(repo_cls):
    assert inspect.isabstract(repo_cls), f"{repo_cls.__name__} is not abstract"
    with pytest.raises(TypeError):
        repo_cls()


@pytest.mark.parametrize("repo_cls", ALL_REPOSITORIES)
def test_repositories_use_abc_and_abstractmethod(repo_cls):
    import abc

    assert issubclass(repo_cls, abc.ABC), f"{repo_cls.__name__} does not use abc.ABC"
    assert repo_cls.__abstractmethods__, f"{repo_cls.__name__} has no abstract methods"
    for name in repo_cls.__abstractmethods__:
        assert getattr(repo_cls, name).__isabstractmethod__ is True


def test_room_repository_type_hints():
    sig_create = inspect.signature(RoomRepository.create)
    assert sig_create.parameters["room"].annotation is Room
    assert inspect.signature(RoomRepository.get).return_annotation == (Room | None)
    assert inspect.signature(RoomRepository.update).parameters["room"].annotation is Room


def test_player_repository_type_hints():
    assert inspect.signature(PlayerRepository.add).parameters["player"].annotation is Player
    get_sig = inspect.signature(PlayerRepository.get)
    assert get_sig.parameters["room_id"].annotation is str
    assert get_sig.parameters["player_id"].annotation is str
    assert get_sig.return_annotation == (Player | None)
    list_sig = inspect.signature(PlayerRepository.list_by_room)
    assert list_sig.return_annotation == list[Player]


def test_puzzle_repository_type_hints():
    assert inspect.signature(PuzzleRepository.save_snapshot).parameters["puzzle"].annotation is Puzzle
    assert inspect.signature(PuzzleRepository.get_snapshot).return_annotation == (Puzzle | None)


def test_answer_repository_type_hints():
    assert inspect.signature(AnswerRepository.save).parameters["answers"].annotation is OfficialAnswers
    assert inspect.signature(AnswerRepository.get).return_annotation == (OfficialAnswers | None)


def test_submission_repository_type_hints():
    assert inspect.signature(SubmissionRepository.add).parameters["submission"].annotation is Submission
    assert inspect.signature(SubmissionRepository.get).return_annotation == (Submission | None)
    assert inspect.signature(SubmissionRepository.list_pending_by_room).return_annotation == list[Submission]
    update_sig = inspect.signature(SubmissionRepository.update_status)
    assert update_sig.parameters["status"].annotation is SubmissionStatus
    assert update_sig.parameters["points"].annotation is int


def test_score_repository_type_hints():
    assert inspect.signature(ScoreRepository.add_event).parameters["event"].annotation is ScoreEvent
    assert inspect.signature(ScoreRepository.list_by_room).return_annotation == list[ScoreEvent]


def test_interfaces_import_domain_models_not_duplicates():
    src = inspect.getsource(interfaces)
    assert "from abc import" in src or "import abc" in src
    assert "OfficialAnswers" in src
    assert "SubmissionStatus" in src
