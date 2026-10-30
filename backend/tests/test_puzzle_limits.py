import io
import time
from dataclasses import replace

import pytest
from PIL import Image

from app.models.puzzle import Cell, Clue, Puzzle
from app.puzzle_tools import google_clues
from app.services import gemini_quota
from app.services import puzzle_image_processor as processor
from app.services.limits import get_limits


def make_puzzle(width=3, height=3, clues=None) -> Puzzle:
    return Puzzle(
        puzzleId="puzzle-limits",
        title="Limits puzzle",
        width=width,
        height=height,
        cells=[
            Cell(
                row=0,
                col=0,
                type="white",
                number=1,
                startsAcross=True,
                startsDown=False,
            )
        ],
        clues=clues if clues is not None else [make_clue()],
    )


def make_clue(clue_id="A1", text="Short clue") -> Clue:
    return Clue(
        clueId=clue_id,
        number=1,
        direction="across",
        text=text,
        answerLength=5,
    )


def test_grid_at_the_limit_is_accepted():
    limits = get_limits()

    processor._validate_puzzle(make_puzzle(20, 20), limits)


def test_grid_larger_than_the_limit_is_rejected():
    limits = get_limits()

    with pytest.raises(processor.PuzzleProcessingError, match="Grid is too large"):
        processor._validate_puzzle(make_puzzle(21, 20), limits)


def test_clue_longer_than_the_limit_is_rejected():
    limits = get_limits()

    with pytest.raises(processor.PuzzleProcessingError, match="too long"):
        processor._validate_puzzle(
            make_puzzle(clues=[make_clue(text="x" * 501)]), limits
        )


def test_too_many_clues_are_rejected():
    limits = replace(get_limits(), max_clues=2)
    clues = [make_clue(f"A{i}") for i in range(3)]

    with pytest.raises(processor.PuzzleProcessingError, match="Too many clues"):
        processor._validate_puzzle(make_puzzle(clues=clues), limits)


def test_gemini_normalizer_rejects_too_many_clues():
    limits = replace(get_limits(), max_clues=2)
    data = [
        {"number": i, "direction": "across", "text": "clue"} for i in range(3)
    ]

    with pytest.raises(ValueError, match="Too many clues"):
        google_clues._normalize(data, limits)


def test_gemini_normalizer_rejects_long_clue_text():
    limits = replace(get_limits(), max_clue_length=5)
    data = [{"number": 1, "direction": "across", "text": "too long"}]

    with pytest.raises(ValueError, match="too long"):
        google_clues._normalize(data, limits)


def test_gemini_normalizer_rejects_non_integer_number():
    data = [{"number": "one", "direction": "across", "text": "clue"}]

    with pytest.raises(ValueError, match="not an integer"):
        google_clues._normalize(data, get_limits())


def test_fallback_is_allowed_only_for_transient_errors():
    assert google_clues._fallback_allowed(RuntimeError("model overloaded")) is True
    assert google_clues._fallback_allowed(ValueError("bad input")) is False
    assert google_clues._fallback_allowed(PermissionError("denied")) is False

    quota_error = RuntimeError("quota exceeded")
    quota_error.code = 429
    assert google_clues._fallback_allowed(quota_error) is False


def test_parser_timeout_returns_a_controlled_error(monkeypatch):
    def slow_parse(_path):
        time.sleep(0.5)
        return make_puzzle()

    fast_limits = replace(get_limits(), parser_timeout_seconds=0.05)
    monkeypatch.setattr(processor, "_parse_local", slow_parse)
    monkeypatch.setattr(processor, "get_limits", lambda: fast_limits)

    with pytest.raises(processor.PuzzleProcessingError, match="timed out"):
        processor.process_image(png_bytes(30, 30))


def test_kill_switch_blocks_processing(monkeypatch):
    monkeypatch.setenv("IMAGE_PARSER_ENABLED", "false")

    with pytest.raises(processor.PuzzleProcessingError, match="disabled"):
        processor.process_image(b"not-a-real-image")

def png_bytes(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_upload_larger_than_the_limit_is_rejected(monkeypatch):
    limits = replace(get_limits(), max_upload_bytes=10)
    monkeypatch.setattr(processor, "get_limits", lambda: limits)

    with pytest.raises(processor.PuzzleProcessingError, match="too large"):
        processor.process_image(b"x" * 11)


def test_image_dimensions_above_the_limit_are_rejected(monkeypatch):
    limits = replace(get_limits(), max_image_dimension=50)
    monkeypatch.setattr(processor, "get_limits", lambda: limits)

    with pytest.raises(processor.PuzzleProcessingError, match="too large"):
        processor.process_image(png_bytes(60, 60))


def test_unreadable_image_is_rejected(monkeypatch):
    with pytest.raises(processor.PuzzleProcessingError, match="could not be read"):
        processor.process_image(b"not-an-image")


def test_quota_fails_closed_when_the_hour_is_full(monkeypatch):
    gemini_quota.reset_quota()
    monkeypatch.setattr(
        gemini_quota,
        "get_limits",
        lambda: replace(get_limits(), gemini_max_per_hour=1),
    )

    gemini_quota.check_and_record()
    with pytest.raises(gemini_quota.QuotaExceeded, match="hourly"):
        gemini_quota.check_and_record()


def test_quota_fails_closed_when_the_day_is_full(monkeypatch):
    gemini_quota.reset_quota()
    monkeypatch.setattr(
        gemini_quota,
        "get_limits",
        lambda: replace(get_limits(), gemini_max_per_day=1),
    )

    gemini_quota.check_and_record()
    with pytest.raises(gemini_quota.QuotaExceeded, match="daily"):
        gemini_quota.check_and_record()
