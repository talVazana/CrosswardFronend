from app.models.puzzle import Cell, Clue, Puzzle
from app.services.puzzle_utils import normalize_answer, validate_puzzle_structure


def cell(row, col, cell_type="white", number=None, starts_across=False, starts_down=False):
    return Cell(
        row=row,
        col=col,
        type=cell_type,
        number=number,
        startsAcross=starts_across,
        startsDown=starts_down,
    )


def clue(clue_id, number, direction, answer_length=3):
    return Clue(
        clueId=clue_id,
        number=number,
        direction=direction,
        text=f"Clue {clue_id}",
        answerLength=answer_length,
    )


def puzzle(cells, clues, width=3, height=3):
    return Puzzle(
        puzzleId="puzzle-006",
        title="Task 006 Puzzle",
        width=width,
        height=height,
        cells=cells,
        clues=clues,
    )


def white_3x3():
    return [
        cell(r, c)
        for r in range(3)
        for c in range(3)
    ]


def with_start(cells, row, col, number, starts_across=False, starts_down=False):
    return [
        cell(
            c.row,
            c.col,
            c.type,
            number if (c.row == row and c.col == col) else c.number,
            starts_across if (c.row == row and c.col == col) else c.startsAcross,
            starts_down if (c.row == row and c.col == col) else c.startsDown,
        )
        for c in cells
    ]


def test_normalize_trims_and_uppercases():
    assert normalize_answer("  aBcDe  ") == "ABCDE"


def test_normalize_collapses_internal_whitespace():
    assert normalize_answer("word  with   multiple   spaces") == "WORD WITH MULTIPLE SPACES"


def test_valid_puzzle_returns_empty_list():
    cells = with_start(white_3x3(), 0, 0, 1, starts_across=True)
    p = puzzle(cells, [clue("A1", 1, "across", answer_length=3)])
    assert validate_puzzle_structure(p) == []


def test_length_mismatch_names_clue():
    cells = with_start(white_3x3(), 0, 0, 1, starts_across=True)
    p = puzzle(cells, [clue("A1", 1, "across", answer_length=5)])
    errors = validate_puzzle_structure(p)
    combined = " ".join(errors)
    assert errors
    assert "A1" in combined
    assert "5" in combined and "3" in combined


def test_start_flag_without_number_is_reported():
    cells = white_3x3()
    cells[0] = cell(0, 0, number=None, starts_across=True)
    p = puzzle(cells, [clue("A1", 1, "across", answer_length=1)])
    errors = validate_puzzle_structure(p)
    combined = " ".join(errors)
    assert errors
    assert "no number" in combined
    assert "(0, 0)" in combined


def test_orphaned_clue_names_clue_id():
    cells = with_start(white_3x3(), 0, 0, 1, starts_across=True)
    p = puzzle(cells, [clue("ORPHAN-9", 9, "across", answer_length=3)])
    errors = validate_puzzle_structure(p)
    combined = " ".join(errors)
    assert errors
    assert "orphaned" in combined
    assert "ORPHAN-9" in combined


def test_shared_numbering_mismatch_is_reported():
    cells = white_3x3()
    cells = with_start(cells, 0, 0, 1, starts_across=True, starts_down=True)
    cells = with_start(cells, 1, 0, 2, starts_down=True)
    p = puzzle(
        cells,
        [
            clue("A1", 1, "across", answer_length=3),
            clue("D2", 2, "down", answer_length=2),
        ],
    )
    errors = validate_puzzle_structure(p)
    combined = " ".join(errors)
    assert errors
    assert "(0, 0)" in combined
    assert "shared number" in combined


def test_normalize_empty_string_returns_empty_string():
    assert normalize_answer("") == ""


def test_normalize_preserves_hebrew_letters():
    assert normalize_answer("   שלום   ") == "שלום"


def test_all_black_grid_is_invalid():
    cells = [cell(r, c, cell_type="black") for r in range(3) for c in range(3)]
    p = puzzle(cells, [clue("A1", 1, "across", answer_length=3)])
    errors = validate_puzzle_structure(p)
    assert errors
    assert "A1" in " ".join(errors)
