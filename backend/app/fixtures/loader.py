import json
from pathlib import Path

from app.models.answers import OfficialAnswers
from app.models.puzzle import Puzzle

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO_ROOT / "fixtures" / "puzzles"


def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Required fixture file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_sample_puzzle() -> tuple[Puzzle, OfficialAnswers]:
    puzzle = Puzzle.model_validate(_load_json(FIXTURES_DIR / "valid_sample_puzzle.json"))
    answers = OfficialAnswers.model_validate(
        _load_json(FIXTURES_DIR / "sample_official_answers.json")
    )
    return puzzle, answers


def load_invalid_puzzle_raw() -> dict:
    return _load_json(FIXTURES_DIR / "invalid_malformed_puzzle.json")
