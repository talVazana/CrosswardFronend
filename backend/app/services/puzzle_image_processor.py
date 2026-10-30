"""Turn an uploaded crossword image into a Puzzle.

Runs the vendored scripts verbatim:

- ``parser.py`` produces the grid matrix JSON.
- ``google_clues.py`` extracts the Hebrew clue list with Gemini.

Then merges both into the backend ``Puzzle`` model using the existing
``normalize_parser_response`` adapter.
"""

from __future__ import annotations

import concurrent.futures
import io
import re
import tempfile
import time
from pathlib import Path

from PIL import Image

from ..adapters.parser_adapter import normalize_parser_response
from ..models.puzzle import Clue, Puzzle
from ..puzzle_tools import google_clues
from ..puzzle_tools import parser as crossword_parser
from . import gemini_quota
from .limits import Limits, get_limits


class PuzzleProcessingError(Exception):
    pass


_parser_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="crossword-parser"
)


def _parse_local(image_path: str) -> Puzzle:
    mat, nr, nc = crossword_parser.parse_crossword_image(image_path)
    parser_json = crossword_parser.generate_crossword_json(mat, nr, nc)
    return normalize_parser_response(parser_json)


def _validate_clues(clues: list[Clue], limits: Limits) -> None:
    if len(clues) > limits.max_clues:
        raise PuzzleProcessingError(
            f"Too many clues: {len(clues)} (max {limits.max_clues})"
        )
    total = 0
    for clue in clues:
        text = clue.text or ""
        if len(text) > limits.max_clue_length:
            raise PuzzleProcessingError(
                f"Clue {clue.clueId} is too long: {len(text)} characters "
                f"(max {limits.max_clue_length})"
            )
        total += len(text)
    if total > limits.max_total_clue_chars:
        raise PuzzleProcessingError(
            f"Clue text is too long: {total} characters "
            f"(max {limits.max_total_clue_chars})"
        )


def _validate_puzzle(puzzle: Puzzle, limits: Limits) -> None:
    if puzzle.width <= 0 or puzzle.height <= 0:
        raise PuzzleProcessingError("Puzzle grid has an invalid size")
    if puzzle.width > limits.max_grid_size or puzzle.height > limits.max_grid_size:
        raise PuzzleProcessingError(
            f"Grid is too large: {puzzle.width}x{puzzle.height} "
            f"(max {limits.max_grid_size}x{limits.max_grid_size})"
        )
    _validate_clues(puzzle.clues, limits)


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


def _validate_upload(image_bytes: bytes, limits: Limits) -> None:
    if len(image_bytes) > limits.max_upload_bytes:
        raise PuzzleProcessingError(
            f"Image is too large: {len(image_bytes)} bytes "
            f"(max {limits.max_upload_bytes})"
        )
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            width, height = image.size
    except Exception as exc:
        raise PuzzleProcessingError("Image could not be read") from exc
    if width > limits.max_image_dimension or height > limits.max_image_dimension:
        raise PuzzleProcessingError(
            f"Image is too large: {width}x{height} pixels "
            f"(max {limits.max_image_dimension})"
        )


def _check_quota() -> None:
    try:
        gemini_quota.check_and_record()
    except gemini_quota.QuotaExceeded as exc:
        raise PuzzleProcessingError(str(exc)) from exc


def process_image(image_bytes: bytes) -> Puzzle:
    limits = get_limits()
    if not limits.image_parser_enabled:
        raise PuzzleProcessingError("Image parsing is disabled")
    if not limits.gemini_extraction_enabled:
        raise PuzzleProcessingError("Clue extraction is disabled")
    _validate_upload(image_bytes, limits)

    deadline = time.monotonic() + limits.image_processing_timeout_seconds

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        future = _parser_pool.submit(_parse_local, tmp_path)
        try:
            puzzle = future.result(timeout=limits.parser_timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            raise PuzzleProcessingError(
                f"Puzzle parsing timed out after {limits.parser_timeout_seconds} seconds"
            ) from exc

        _validate_puzzle(puzzle, limits)

        remaining = deadline - time.monotonic()
        if remaining < 1:
            raise PuzzleProcessingError(
                "Image processing timed out after "
                f"{limits.image_processing_timeout_seconds} seconds"
            )

        _check_quota()
        clues_raw = google_clues.extract_clues(
            tmp_path,
            timeout_seconds=max(1, min(limits.gemini_timeout_seconds, int(remaining))),
            max_attempts=limits.gemini_max_attempts,
            limits=limits,
        )
        display_clues = _clues_from_google(clues_raw)
        _validate_clues(display_clues, limits)
        return _merge_clue_texts(puzzle, display_clues)
    except PuzzleProcessingError:
        raise
    except Exception as exc:
        raise PuzzleProcessingError(f"Puzzle processing failed: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)
