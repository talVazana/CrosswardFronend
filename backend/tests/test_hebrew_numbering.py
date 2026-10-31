from pathlib import Path

import cv2
import pytest

from app.adapters.parser_adapter import normalize_parser_response
from app.api.routes import rooms as rooms_module
from app.models.puzzle import Clue, Puzzle
from app.puzzle_tools import parser as crossword_parser
from app.repositories.in_memory import (
    InMemoryPlayerRepository,
    InMemoryRoomRepository,
    InMemoryScoreRepository,
)
from app.services import firestore_loader, firestore_publisher, scoring_service
from app.services.puzzle_numbering import (
    is_puzzle_numbering_consistent,
    repair_puzzle_numbering,
)
from app.services.scoring_service import ScoringService

IMAGE_PATH = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "public"
    / "puzzle-source.jpg"
)


def _sample_matrix() -> list[list[int]]:
    return [
        [1, 1, 1],
        [1, 0, 1],
        [1, 1, 1],
    ]


def _legacy_puzzle() -> tuple[Puzzle, list[Clue]]:
    expected = normalize_parser_response(
        crossword_parser.generate_crossword_json(_sample_matrix(), 3, 3)
    )
    display_clues = [
        clue.model_copy(update={"text": f"Visible {clue.clueId}"})
        for clue in expected.clues
    ]
    legacy_cells = [
        cell.model_copy(
            update={
                "number": 1 if cell.number == 1 else None,
                "startsAcross": cell.startsAcross if cell.number == 1 else False,
                "startsDown": cell.startsDown if cell.number == 1 else False,
            }
        )
        for cell in expected.cells
    ]
    legacy = Puzzle(
        puzzleId="legacy-puzzle",
        title="Legacy Puzzle",
        width=3,
        height=3,
        cells=legacy_cells,
        clues=[expected.clues[0].model_copy(update={"text": "Old internal text"})],
        displayClues=display_clues,
    )
    return legacy, display_clues


def test_hebrew_numbering_scans_top_to_bottom_right_to_left():
    result = crossword_parser.generate_crossword_json(_sample_matrix(), 3, 3)

    assert result["clues"] == [
        {"clue_number": 1, "row": 0, "col": 2, "horizontal": True, "vertical": True},
        {"clue_number": 2, "row": 0, "col": 0, "horizontal": False, "vertical": True},
        {"clue_number": 3, "row": 2, "col": 2, "horizontal": True, "vertical": False},
    ]
    assert result["matrix"] == [
        [2, 1, 2],
        [1, 0, 1],
        [1, 1, 2],
    ]


def test_printed_digit_marks_do_not_affect_numbering():
    plain = crossword_parser.generate_crossword_json(_sample_matrix(), 3, 3)
    marked = crossword_parser.generate_crossword_json(
        [
            [2, 1, 1],
            [1, 0, 2],
            [1, 1, 1],
        ],
        3,
        3,
    )

    assert marked == plain


@pytest.mark.skipif(not IMAGE_PATH.exists(), reason="sample crossword image missing")
def test_parser_output_is_scale_invariant(monkeypatch):
    source = cv2.imread(str(IMAGE_PATH))
    assert source is not None

    results = []
    for scale in (0.5, 1.0, 3.0):
        image = cv2.resize(
            source,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC,
        )
        original_imread = crossword_parser.cv2.imread
        crossword_parser.cv2.imread = lambda _path, _image=image: _image
        try:
            matrix, rows, cols = crossword_parser.parse_crossword_image("unused")
            results.append(
                crossword_parser.generate_crossword_json(matrix, rows, cols)
            )
        finally:
            crossword_parser.cv2.imread = original_imread

    assert results[0] == results[1] == results[2]


def test_repair_rebuilds_matrix_and_preserves_clue_list():
    legacy, display_clues = _legacy_puzzle()
    assert not is_puzzle_numbering_consistent(legacy)

    repaired = repair_puzzle_numbering(legacy)

    assert is_puzzle_numbering_consistent(repaired)
    assert repaired.displayClues == display_clues
    assert {clue.clueId: clue.text for clue in repaired.clues} == {
        clue.clueId: clue.text for clue in display_clues
    }
    assert [cell for cell in repaired.cells if cell.number is not None] == [
        cell
        for cell in normalize_parser_response(
            crossword_parser.generate_crossword_json(_sample_matrix(), 3, 3)
        ).cells
        if cell.number is not None
    ]


def test_repair_is_idempotent():
    repaired = repair_puzzle_numbering(_legacy_puzzle()[0])

    assert repair_puzzle_numbering(repaired) == repaired


def test_restore_rooms_repairs_legacy_puzzle(monkeypatch):
    legacy, _ = _legacy_puzzle()
    document = {
        "roomId": "legacy-room",
        "title": "Legacy Room",
        "status": "active",
        "puzzle": legacy.model_dump(),
        "players": [],
        "scores": [],
        "solvedClues": [],
    }
    room_repository = InMemoryRoomRepository()
    player_repository = InMemoryPlayerRepository()

    monkeypatch.setattr(
        firestore_publisher,
        "read_collection",
        lambda collection: [document] if collection == "rooms" else [],
    )
    monkeypatch.setattr(rooms_module, "room_repository", room_repository)
    monkeypatch.setattr(rooms_module, "player_repository", player_repository)
    monkeypatch.setattr(
        scoring_service,
        "_default_service",
        ScoringService(InMemoryScoreRepository()),
    )

    firestore_loader._restore_rooms()

    room = room_repository.get("legacy-room")
    assert room is not None
    assert is_puzzle_numbering_consistent(room.puzzleSnapshot)
    assert room.puzzleSnapshot.displayClues == legacy.displayClues
