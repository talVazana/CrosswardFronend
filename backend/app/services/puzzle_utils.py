import re

from app.models.puzzle import Cell, Clue, Puzzle


def normalize_answer(raw_answer: str) -> str:
    return re.sub(r"\s+", " ", raw_answer.strip()).upper()


def _cell_at(puzzle: Puzzle, row: int, col: int) -> Cell | None:
    for cell in puzzle.cells:
        if cell.row == row and cell.col == col:
            return cell
    return None


def _count_white(puzzle: Puzzle, start: Cell, direction: str) -> int:
    count = 0
    row, col = start.row, start.col
    while True:
        cell = _cell_at(puzzle, row, col)
        if cell is None or cell.type == "black":
            break
        count += 1
        if direction == "across":
            col -= 1
        else:
            row += 1
    return count


def _find_start_cells(puzzle: Puzzle, clue: Clue) -> list[Cell]:
    return [
        cell
        for cell in puzzle.cells
        if cell.number == clue.number
        and cell.type == "white"
        and (
            (clue.direction == "across" and cell.startsAcross)
            or (clue.direction == "down" and cell.startsDown)
        )
    ]


def validate_puzzle_structure(puzzle: Puzzle) -> list[str]:
    errors: list[str] = []

    for clue in puzzle.clues:
        starts = _find_start_cells(puzzle, clue)
        if not starts:
            errors.append(
                f"Clue {clue.clueId} (number {clue.number}, {clue.direction}) is "
                f"orphaned: no start cell found"
            )
            continue
        if len(starts) > 1:
            errors.append(
                f"Clue {clue.clueId} (number {clue.number}, {clue.direction}) is "
                f"ambiguous: {len(starts)} start cells match"
            )
            continue
        start = starts[0]
        length = _count_white(puzzle, start, clue.direction)
        if length != clue.answerLength:
            errors.append(
                f"Clue {clue.clueId} answerLength is {clue.answerLength} but grid "
                f"has {length} white cells from ({start.row}, {start.col}) "
                f"{clue.direction}"
            )

    for cell in puzzle.cells:
        if (cell.startsAcross or cell.startsDown) and cell.number is None:
            errors.append(
                f"Cell ({cell.row}, {cell.col}) has a start flag set but no number"
            )

    for cell in puzzle.cells:
        if cell.startsAcross and cell.startsDown:
            across_clues = [
                c
                for c in puzzle.clues
                if c.direction == "across" and c.number == cell.number
            ]
            down_clues = [
                c
                for c in puzzle.clues
                if c.direction == "down" and c.number == cell.number
            ]
            ok = len(across_clues) == 1 and len(down_clues) == 1
            if ok:
                across_starts = _find_start_cells(puzzle, across_clues[0])
                down_starts = _find_start_cells(puzzle, down_clues[0])
                ok = (
                    len(across_starts) == 1
                    and across_starts[0] is cell
                    and len(down_starts) == 1
                    and down_starts[0] is cell
                )
            if not ok:
                errors.append(
                    f"Cell ({cell.row}, {cell.col}) has both start flags set but "
                    f"does not resolve to exactly one across and one down clue "
                    f"with shared number {cell.number}"
                )

    return errors
