import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.adapters.parser_adapter import (
    ParserConfigError,
    ParserSchemaError,
    ParserTimeoutError,
    PuzzleParserAdapter,
    normalize_parser_response,
)
from app.models.puzzle import Puzzle

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "parser-responses"
    / "sample_parser_output.json"
)


def _sample_payload():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _adapter():
    return PuzzleParserAdapter()


class _Handler(BaseHTTPRequestHandler):
    response_body = b"{}"
    response_status = 200
    delay_seconds = 0.0

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        self.send_response(self.response_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.response_body)

    def log_message(self, *args):
        pass


def _serve(body: dict, delay_seconds: float = 0.0, status: int = 200):
    handler = type(
        "_Task035Handler",
        (_Handler,),
        {
            "response_body": json.dumps(body).encode("utf-8"),
            "response_status": status,
            "delay_seconds": delay_seconds,
        },
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/parse"
    return server, url


def test_fixture_mode_returns_schema_without_network(monkeypatch):
    def forbidden_urlopen(*args, **kwargs):
        raise AssertionError("fixture mode must not perform network I/O")

    monkeypatch.setattr(
        "app.adapters.parser_adapter.urllib.request.urlopen", forbidden_urlopen
    )
    raw = _adapter().parse_image(b"image-bytes", use_fixture=True)
    assert isinstance(raw, dict)
    assert set(("rows", "cols", "matrix", "clues")).issubset(raw.keys())
    assert raw["rows"] == 5
    assert raw["cols"] == 5
    assert len(raw["matrix"]) == 5
    assert raw["clues"]


def test_adapter_exposes_normalize_parser_response_method():
    assert hasattr(PuzzleParserAdapter, "normalize_parser_response"), (
        "Task requires PuzzleParserAdapter with normalize_parser_response(raw) -> Puzzle"
    )


def test_fixture_payload_normalizes_to_puzzle():
    raw = _adapter().parse_image(b"", use_fixture=True)
    puzzle = normalize_parser_response(raw)
    assert isinstance(puzzle, Puzzle)
    assert puzzle.width == raw["cols"]
    assert puzzle.height == raw["rows"]
    assert len(puzzle.cells) == raw["rows"] * raw["cols"]

    by_pos = {(cell.row, cell.col): cell for cell in puzzle.cells}
    assert by_pos[(1, 1)].type == "black"
    assert by_pos[(0, 1)].type == "white"
    assert by_pos[(0, 1)].number is None
    assert by_pos[(0, 0)].number == 1
    assert by_pos[(0, 0)].startsAcross is True
    assert by_pos[(0, 0)].startsDown is True
    assert by_pos[(0, 4)].number == 2
    assert by_pos[(0, 4)].startsAcross is False
    assert by_pos[(0, 4)].startsDown is True
    assert by_pos[(1, 2)].number == 3


def test_both_directions_share_number():
    puzzle = normalize_parser_response(_sample_payload())
    across = {clue.clueId: clue for clue in puzzle.clues if clue.direction == "across"}
    down = {clue.clueId: clue for clue in puzzle.clues if clue.direction == "down"}
    assert "A1" in across and "D1" in down
    assert across["A1"].number == down["D1"].number == 1
    assert "A2" not in across
    assert "D3" not in down
    assert "A3" in across
    assert "D2" in down


def test_across_answer_length_counts_right_to_left():
    payload = {
        "rows": 4,
        "cols": 6,
        "matrix": [
            [1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1],
            [1, 0, 1, 1, 1, 2],
            [1, 1, 1, 1, 1, 1],
        ],
        "clues": [
            {"clue_number": 1, "row": 2, "col": 5, "horizontal": True, "vertical": False}
        ],
    }
    puzzle = normalize_parser_response(payload)
    across = [clue for clue in puzzle.clues if clue.clueId == "A1"]
    assert len(across) == 1
    assert across[0].answerLength == 4


def test_down_answer_length_counts_downward():
    puzzle = normalize_parser_response(_sample_payload())
    down = {clue.clueId: clue for clue in puzzle.clues if clue.direction == "down"}
    assert down["D1"].answerLength == 5


def test_clue_text_defaults_to_empty():
    puzzle = normalize_parser_response(_sample_payload())
    assert puzzle.clues
    assert all(clue.text == "" for clue in puzzle.clues)


def test_unset_api_url_raises_config_error(monkeypatch):
    monkeypatch.delenv("PARSER_API_URL", raising=False)
    with pytest.raises(ParserConfigError):
        _adapter().parse_image(b"image-bytes", use_fixture=False)


def test_timeout_is_wrapped_in_domain_exception(monkeypatch):
    server, url = _serve({}, delay_seconds=15)
    monkeypatch.setenv("PARSER_API_URL", url)
    started = time.monotonic()
    try:
        with pytest.raises(ParserTimeoutError):
            _adapter().parse_image(b"image-bytes", use_fixture=False)
        elapsed = time.monotonic() - started
        assert elapsed < 12, f"timeout took {elapsed:.1f}s, expected ~10s"
    finally:
        server.shutdown()
        server.server_close()


def test_bad_schema_raises_domain_exception(monkeypatch):
    server, url = _serve({"bad": "schema"})
    monkeypatch.setenv("PARSER_API_URL", url)
    try:
        raw = _adapter().parse_image(b"image-bytes", use_fixture=False)
        assert raw == {"bad": "schema"}
        with pytest.raises(ParserSchemaError):
            normalize_parser_response(raw)
    finally:
        server.shutdown()
        server.server_close()


def test_numbered_cell_without_clue_raises_schema_error():
    payload = {
        "rows": 2,
        "cols": 2,
        "matrix": [[2, 1], [1, 1]],
        "clues": [],
    }
    with pytest.raises(ParserSchemaError):
        normalize_parser_response(payload)


def test_http_500_is_wrapped_in_domain_exception(monkeypatch):
    server, url = _serve({"error": "boom"}, status=500)
    monkeypatch.setenv("PARSER_API_URL", url)
    try:
        with pytest.raises((ParserSchemaError, ParserTimeoutError, ParserConfigError)):
            _adapter().parse_image(b"image-bytes", use_fixture=False)
    finally:
        server.shutdown()
        server.server_close()
