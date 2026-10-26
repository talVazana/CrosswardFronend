"""Turn an uploaded crossword image into a Puzzle.

Runs the vendored scripts verbatim:

- ``parser.py`` produces the grid matrix JSON.
- ``google_clues.py`` extracts the Hebrew clue list with Gemini.

Then merges both into the backend ``Puzzle`` model using the existing
``normalize_parser_response`` adapter.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from ..adapters.parser_adapter import normalize_parser_response
from ..models.puzzle import Clue, Puzzle
from ..puzzle_tools import google_clues
from ..puzzle_tools import parser as crossword_parser


class PuzzleProcessingError(Exception):
    pass


def _answer_length(text: str) -> int:
    groups = re.findall(r"\(([\d,\s]+)\)", text)
    if not groups:
        return 1
    return (
        sum(int(part) for part in groups[-1].split(",") if part.strip().isdigit())
        or 1
    )


def _clues_from_google(clues_raw: list[dict]) -> list[Clue]:
    clues: list[Clue] = []
    for entry in clues_raw:
        number = entry["number"]
        direction = entry["direction"]
        prefix = "A" if direction == "across" else "D"
        clues.append(
            Clue(
                clueId=f"{prefix}{number}",
                number=number,
                direction=direction,
                text=entry["text"],
                answerLength=_answer_length(entry["text"]),
            )
        )
    return clues


def _merge_clue_texts(puzzle: Puzzle, display_clues: list[Clue]) -> Puzzle:
    text_by_clue = {clue.clueId: clue.text for clue in display_clues}
    grid_ids = {clue.clueId for clue in puzzle.clues}
    unmatched = [clue for clue in display_clues if clue.clueId not in grid_ids]

    merged_clues: list[Clue] = []
    for clue in puzzle.clues:
        if clue.clueId in text_by_clue:
            merged_clues.append(
                clue.model_copy(update={"text": text_by_clue[clue.clueId]})
            )
            continue
        match = next(
            (
                candidate
                for candidate in unmatched
                if candidate.direction == clue.direction
                and candidate.answerLength == clue.answerLength
            ),
            None,
        )
        if match is not None:
            unmatched.remove(match)
            merged_clues.append(clue.model_copy(update={"text": match.text}))
        else:
            merged_clues.append(clue)

    return puzzle.model_copy(
        update={"clues": merged_clues, "displayClues": display_clues}
    )


def process_image(image_bytes: bytes) -> Puzzle:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        mat, nr, nc = crossword_parser.parse_crossword_image(tmp_path)
        parser_json = crossword_parser.generate_crossword_json(mat, nr, nc)
        puzzle = normalize_parser_response(parser_json)

        clues_raw = google_clues.extract_clues(tmp_path)
        display_clues = _clues_from_google(clues_raw)
        return _merge_clue_texts(puzzle, display_clues)
    except PuzzleProcessingError:
        raise
    except Exception as exc:
        raise PuzzleProcessingError(f"Puzzle processing failed: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)
