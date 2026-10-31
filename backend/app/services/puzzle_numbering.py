from __future__ import annotations

from ..adapters.parser_adapter import normalize_parser_response
from ..models.puzzle import Cell, Clue, Puzzle
from ..puzzle_tools.parser import generate_crossword_json


def _matrix_from_puzzle(puzzle: Puzzle) -> list[list[int]]:
    matrix = [[0 for _ in range(puzzle.width)] for _ in range(puzzle.height)]
    for cell in puzzle.cells:
        matrix[cell.row][cell.col] = 0 if cell.type == "black" else 1
    return matrix


def _run_length(
    cells: dict[tuple[int, int], Cell], cell: Cell, direction: str
) -> int:
    step_row, step_col = (0, -1) if direction == "across" else (1, 0)
    length = 0
    row, col = cell.row, cell.col
    while True:
        current = cells.get((row, col))
        if current is None or current.type == "black":
            break
        length += 1
        row += step_row
        col += step_col
    return length


def is_puzzle_numbering_consistent(puzzle: Puzzle) -> bool:
    cells = {(cell.row, cell.col): cell for cell in puzzle.cells}
    clues_by_id: dict[str, list[Clue]] = {}
    for clue in puzzle.clues:
        clues_by_id.setdefault(clue.clueId, []).append(clue)

    for clue in puzzle.clues:
        expected_id = ("A" if clue.direction == "across" else "D") + str(clue.number)
        if clue.clueId != expected_id:
            return False
        matches = [
            cell
            for cell in puzzle.cells
            if cell.number == clue.number
            and cell.type == "white"
            and (
                (clue.direction == "across" and cell.startsAcross)
                or (clue.direction == "down" and cell.startsDown)
            )
        ]
        if len(matches) != 1:
            return False
        if _run_length(cells, matches[0], clue.direction) != clue.answerLength:
            return False

    for cell in puzzle.cells:
        if cell.number is None:
            if cell.startsAcross or cell.startsDown:
                return False
            continue
        if not (cell.startsAcross or cell.startsDown):
            return False
        if cell.startsAcross and len(clues_by_id.get(f"A{cell.number}", [])) != 1:
            return False
        if cell.startsDown and len(clues_by_id.get(f"D{cell.number}", [])) != 1:
            return False

    return True


def repair_puzzle_numbering(puzzle: Puzzle) -> Puzzle:
    if is_puzzle_numbering_consistent(puzzle):
        return puzzle

    matrix = _matrix_from_puzzle(puzzle)
    raw = generate_crossword_json(matrix, puzzle.height, puzzle.width)
    rebuilt = normalize_parser_response(raw)

    text_by_clue = {clue.clueId: clue.text for clue in puzzle.clues}
    for clue in puzzle.displayClues or []:
        if clue.text:
            text_by_clue[clue.clueId] = clue.text

    repaired_clues = [
        clue.model_copy(update={"text": text_by_clue.get(clue.clueId, "")})
        for clue in rebuilt.clues
    ]

    return puzzle.model_copy(
        update={"cells": rebuilt.cells, "clues": repaired_clues}
    )
