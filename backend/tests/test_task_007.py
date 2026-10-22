from pathlib import Path

import pytest
from pydantic import ValidationError

from app.fixtures import loader
from app.fixtures.loader import load_invalid_puzzle_raw, load_sample_puzzle
from app.models.answers import OfficialAnswers
from app.models.puzzle import Puzzle

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


def test_returns_puzzle_and_answers_tuple_when_cwd_is_backend(monkeypatch):
    monkeypatch.chdir(BACKEND_DIR)
    result = load_sample_puzzle()
    assert isinstance(result, tuple)
    assert len(result) == 2
    puzzle, answers = result
    assert isinstance(puzzle, Puzzle)
    assert isinstance(answers, OfficialAnswers)


def test_cell_0_0_is_shared_across_and_down_start():
    puzzle, _ = load_sample_puzzle()
    cell = next(c for c in puzzle.cells if c.row == 0 and c.col == 0)
    assert cell.number == 1
    assert cell.startsAcross is True
    assert cell.startsDown is True


def test_dimensions_are_5x5():
    puzzle, _ = load_sample_puzzle()
    assert puzzle.width == 5
    assert puzzle.height == 5


def test_answers_cover_every_clue():
    puzzle, answers = load_sample_puzzle()
    clue_ids = [clue.clueId for clue in puzzle.clues]
    assert "A1" in clue_ids
    assert "D1" in clue_ids
    for clue_id in clue_ids:
        assert clue_id in answers.answers, f"missing answer for {clue_id}"
        assert isinstance(answers.answers[clue_id], str)
        assert answers.answers[clue_id].strip() != "", f"empty answer for {clue_id}"


def test_invalid_raw_raises_validation_error():
    raw = load_invalid_puzzle_raw()
    assert isinstance(raw, dict)
    with pytest.raises(ValidationError):
        Puzzle.model_validate(raw)


def test_missing_fixture_raises_file_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(loader, "FIXTURES_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        load_sample_puzzle()
    with pytest.raises(FileNotFoundError):
        load_invalid_puzzle_raw()


def test_path_resolution_independent_of_cwd(monkeypatch, tmp_path):
    assert loader.REPO_ROOT == REPO_ROOT
    monkeypatch.chdir(tmp_path)
    puzzle, answers = load_sample_puzzle()
    assert isinstance(puzzle, Puzzle)
    assert isinstance(answers, OfficialAnswers)
