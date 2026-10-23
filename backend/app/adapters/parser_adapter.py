import json
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path

from app.models.puzzle import Cell, Clue, Puzzle

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "parser-responses"
    / "sample_parser_output.json"
)
PARSER_TIMEOUT_SECONDS = 10


class ParserSchemaError(Exception):
    pass


class ParserTimeoutError(Exception):
    pass


class ParserConfigError(Exception):
    pass


def _count_consecutive_white(matrix: list[list[int]], row: int, col: int, d_row: int, d_col: int) -> int:
    count = 0
    r, c = row, col
    while 0 <= r < len(matrix) and 0 <= c < len(matrix[0]):
        if matrix[r][c] == 0:
            break
        count += 1
        r += d_row
        c += d_col
    return count


def normalize_parser_response(raw: dict) -> Puzzle:
    try:
        rows = raw["rows"]
        cols = raw["cols"]
        matrix = raw["matrix"]
        clues_raw = raw["clues"]
    except (KeyError, TypeError) as exc:
        raise ParserSchemaError(f"Missing required parser field: {exc}") from exc

    if not isinstance(rows, int) or not isinstance(cols, int) or rows < 1 or cols < 1:
        raise ParserSchemaError("rows and cols must be positive integers")
    if not isinstance(matrix, list) or len(matrix) != rows:
        raise ParserSchemaError("matrix must be a list with rows rows")
    for matrix_row in matrix:
        if not isinstance(matrix_row, list) or len(matrix_row) != cols:
            raise ParserSchemaError("each matrix row must have cols entries")

    clue_by_pos: dict[tuple[int, int], dict] = {}
    numbers_seen: set[int] = set()
    for clue in clues_raw:
        try:
            number = clue["clue_number"]
            r = clue["row"]
            c = clue["col"]
            horizontal = clue["horizontal"]
            vertical = clue["vertical"]
        except (KeyError, TypeError) as exc:
            raise ParserSchemaError(f"Clue entry missing field: {exc}") from exc
        if number in numbers_seen:
            raise ParserSchemaError(f"Duplicate clue number {number}")
        numbers_seen.add(number)
        if not (0 <= r < rows and 0 <= c < cols):
            raise ParserSchemaError(f"Clue {number} position ({r}, {c}) out of bounds")
        if (r, c) in clue_by_pos:
            raise ParserSchemaError(f"Duplicate clue at position ({r}, {c})")
        clue_by_pos[(r, c)] = clue

    cells: list[Cell] = []
    for r in range(rows):
        for c in range(cols):
            value = matrix[r][c]
            if value not in (0, 1, 2):
                raise ParserSchemaError(f"Invalid matrix value {value} at ({r}, {c})")
            clue = clue_by_pos.get((r, c))
            if value == 2 and clue is None:
                raise ParserSchemaError(f"Cell ({r}, {c}) is numbered (2) but has no clue entry")
            if value != 2 and clue is not None:
                raise ParserSchemaError(f"Clue {clue['clue_number']} points at non-numbered cell ({r}, {c})")
            cells.append(
                Cell(
                    row=r,
                    col=c,
                    type="black" if value == 0 else "white",
                    number=clue["clue_number"] if clue else None,
                    startsAcross=bool(clue["horizontal"]) if clue else False,
                    startsDown=bool(clue["vertical"]) if clue else False,
                )
            )

    clues: list[Clue] = []
    for clue in clues_raw:
        number = clue["clue_number"]
        r = clue["row"]
        c = clue["col"]
        if clue["horizontal"]:
            length = _count_consecutive_white(matrix, r, c, 0, -1)
            if length < 1:
                raise ParserSchemaError(f"Across clue {number} has no white cells")
            clues.append(
                Clue(
                    clueId=f"A{number}",
                    number=number,
                    direction="across",
                    text="",
                    answerLength=length,
                )
            )
        if clue["vertical"]:
            length = _count_consecutive_white(matrix, r, c, 1, 0)
            if length < 1:
                raise ParserSchemaError(f"Down clue {number} has no white cells")
            clues.append(
                Clue(
                    clueId=f"D{number}",
                    number=number,
                    direction="down",
                    text="",
                    answerLength=length,
                )
            )

    return Puzzle(
        puzzleId="parsed-puzzle",
        title="Parsed Puzzle",
        width=cols,
        height=rows,
        cells=cells,
        clues=clues,
    )


class PuzzleParserAdapter:
    def parse_image(self, image_bytes: bytes, use_fixture: bool = False) -> dict:
        if use_fixture:
            with FIXTURE_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        api_url = os.environ.get("PARSER_API_URL", "")
        if not api_url:
            raise ParserConfigError("PARSER_API_URL environment variable is not set")
        request = urllib.request.Request(
            api_url,
            data=image_bytes,
            method="POST",
            headers={"Content-Type": "application/octet-stream"},
        )
        try:
            with urllib.request.urlopen(request, timeout=PARSER_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except (TimeoutError, socket.timeout, OSError, urllib.error.URLError) as exc:
            if isinstance(getattr(exc, "reason", None), (TimeoutError, socket.timeout)) or "timed out" in str(exc).lower():
                raise ParserTimeoutError(f"Parser service timed out after {PARSER_TIMEOUT_SECONDS}s") from exc
            raise ParserTimeoutError(f"Parser request failed: {exc}") from exc

    def normalize_parser_response(self, raw: dict) -> Puzzle:
        return normalize_parser_response(raw)
