import pytest
from pydantic import ValidationError

from app.models.answers import OfficialAnswers
from app.models.puzzle import Cell, Clue, Puzzle


def make_cell(**overrides):
    data = {
        "row": 0,
        "col": 0,
        "type": "white",
        "number": 1,
        "startsAcross": True,
        "startsDown": False,
    }
    data.update(overrides)
    return data


def make_clue(**overrides):
    data = {
        "clueId": "A1",
        "number": 1,
        "direction": "across",
        "text": "First across entry",
        "answerLength": 5,
    }
    data.update(overrides)
    return data


def make_puzzle(**overrides):
    data = {
        "puzzleId": "puzzle-1",
        "title": "Test Puzzle",
        "width": 3,
        "height": 3,
        "cells": [
            make_cell(row=0, col=0, type="white", number=1),
            make_cell(row=0, col=1, type="black", number=None, startsAcross=False),
            make_cell(row=1, col=0, type="white", number=2, startsAcross=False, startsDown=True),
        ],
        "clues": [
            make_clue(),
            make_clue(
                clueId="D1",
                number=2,
                direction="down",
                text="First down entry",
                answerLength=3,
            ),
        ],
    }
    data.update(overrides)
    return data


def test_valid_puzzle_3x3_created_with_correct_fields():
    puzzle = Puzzle(**make_puzzle())

    assert puzzle.width == 3
    assert puzzle.height == 3
    assert len(puzzle.cells) == 3
    assert len(puzzle.clues) == 2
    assert puzzle.puzzleId == "puzzle-1"
    assert puzzle.title == "Test Puzzle"
    assert puzzle.cells[0].row == 0
    assert puzzle.cells[0].col == 0
    assert puzzle.cells[0].type == "white"
    assert puzzle.cells[0].number == 1
    assert puzzle.cells[0].startsAcross is True
    assert puzzle.cells[0].startsDown is False
    assert puzzle.clues[0].clueId == "A1"
    assert puzzle.clues[0].direction == "across"


def test_cell_row_equal_to_height_raises_validation_error():
    with pytest.raises(ValidationError):
        Puzzle(**make_puzzle(cells=[make_cell(row=3, col=0)]))


def test_cell_col_equal_to_width_raises_validation_error():
    with pytest.raises(ValidationError):
        Puzzle(**make_puzzle(cells=[make_cell(row=0, col=3)]))


def test_cell_negative_col_raises_validation_error():
    with pytest.raises(ValidationError):
        Cell(**make_cell(col=-1))


def test_clue_number_zero_raises_validation_error():
    with pytest.raises(ValidationError):
        Clue(**make_clue(number=0))


def test_clue_answer_length_zero_raises_validation_error():
    with pytest.raises(ValidationError):
        Clue(**make_clue(answerLength=0))


def test_puzzle_empty_cells_raises_validation_error():
    with pytest.raises(ValidationError):
        Puzzle(**make_puzzle(cells=[]))


def test_puzzle_empty_clues_raises_validation_error():
    with pytest.raises(ValidationError):
        Puzzle(**make_puzzle(clues=[]))


def test_cell_type_gray_raises_validation_error():
    with pytest.raises(ValidationError):
        Cell(**make_cell(type="gray"))


def test_clue_direction_diagonal_raises_validation_error():
    with pytest.raises(ValidationError):
        Clue(**make_clue(direction="diagonal"))


def test_puzzle_model_dump_contains_no_official_answers():
    puzzle = Puzzle(**make_puzzle())
    dumped = puzzle.model_dump()

    answer_keys = {"answer", "answers", "officialAnswer", "officialAnswers"}

    def collect_keys(value):
        keys = set()
        if isinstance(value, dict):
            for key, nested in value.items():
                keys.add(key)
                keys |= collect_keys(nested)
        elif isinstance(value, list):
            for item in value:
                keys |= collect_keys(item)
        return keys

    assert answer_keys.isdisjoint(collect_keys(dumped))
    assert "HELLO" not in repr(dumped)
    assert "WORLD" not in repr(dumped)


def test_puzzle_schema_has_no_official_answer_fields():
    schema = Puzzle.model_json_schema()
    properties = schema.get("properties", {})
    assert "answer" not in properties
    assert "answers" not in properties
    assert "officialAnswer" not in properties
    assert "officialAnswers" not in properties


def test_official_answers_stores_mapping_under_puzzle_id():
    answers = OfficialAnswers(puzzleId="puzzle-1", answers={"A1": "HELLO", "D1": "WORLD"})

    assert answers.puzzleId == "puzzle-1"
    assert answers.answers == {"A1": "HELLO", "D1": "WORLD"}


def test_official_answers_is_separate_model_from_puzzle():
    assert OfficialAnswers is not Puzzle
    assert not issubclass(OfficialAnswers, Puzzle)
    assert OfficialAnswers.__module__ != Puzzle.__module__


def test_50x50_grid_in_bounds_instantiates_successfully():
    cells = [
        make_cell(row=row, col=col, number=None, startsAcross=False, startsDown=False)
        for row in range(50)
        for col in range(50)
    ]
    puzzle = Puzzle(**make_puzzle(width=50, height=50, cells=cells))

    assert puzzle.width == 50
    assert puzzle.height == 50
    assert len(puzzle.cells) == 2500


def test_clue_direction_is_case_sensitive():
    with pytest.raises(ValidationError):
        Clue(**make_clue(direction="Across"))
    with pytest.raises(ValidationError):
        Clue(**make_clue(direction="DOWN"))
