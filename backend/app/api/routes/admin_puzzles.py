import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ValidationError

from ...adapters.parser_adapter import (
    ParserConfigError,
    ParserSchemaError,
    ParserTimeoutError,
    PuzzleParserAdapter,
    normalize_parser_response,
)
from ...models.answers import OfficialAnswers
from ...models.puzzle import Puzzle
from ...repositories.in_memory import (
    InMemoryAnswerRepository,
    InMemoryPuzzleRepository,
)
from ...repositories.interfaces import AnswerRepository, PuzzleRepository
from ...services.puzzle_utils import validate_puzzle_structure
from . import admin as admin_module
from . import rooms as rooms_module

router = APIRouter()

puzzle_repository: PuzzleRepository = InMemoryPuzzleRepository()
answer_repository: AnswerRepository = admin_module.answer_repository
parser_adapter = PuzzleParserAdapter()


class PuzzleSaveRequest(BaseModel):
    puzzle: Puzzle
    officialAnswers: OfficialAnswers


def _resolve_admin(request: Request):
    session_token = request.cookies.get(rooms_module.SESSION_COOKIE_NAME)
    if session_token is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    session = rooms_module._sessions.get(session_token)
    if session is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    _, player_id = session
    player = rooms_module.player_repository.get(session[0], player_id)
    if player is None or player.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return player


@router.post("/admin/puzzles/parse")
async def parse_puzzle(request: Request):
    _resolve_admin(request)

    content_type = request.headers.get("content-type", "")
    use_fixture = False
    image_bytes: bytes | None = None
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("image")
        if upload is not None and hasattr(upload, "read"):
            image_bytes = await upload.read()
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        use_fixture = bool(body.get("use_fixture", False))

    try:
        if image_bytes is not None:
            raw = parser_adapter.parse_image(image_bytes, use_fixture=False)
        else:
            raw = parser_adapter.parse_image(b"", use_fixture=use_fixture)
        puzzle = normalize_parser_response(raw)
    except (ParserSchemaError, ParserTimeoutError, ParserConfigError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors())

    errors = validate_puzzle_structure(puzzle)
    return {"puzzle": puzzle, "validation_errors": errors}


@router.post("/admin/puzzles", status_code=201)
def save_puzzle(request: Request, body: PuzzleSaveRequest):
    _resolve_admin(request)

    puzzle = body.puzzle
    official_answers = body.officialAnswers

    if official_answers.puzzleId != puzzle.puzzleId:
        raise HTTPException(
            status_code=400,
            detail="officialAnswers.puzzleId must match puzzle.puzzleId",
        )

    errors = validate_puzzle_structure(puzzle)
    clue_ids = {clue.clueId for clue in puzzle.clues}
    missing = sorted(clue_ids - set(official_answers.answers.keys()))
    if missing:
        errors.append(
            f"Missing official answers for clues: {', '.join(missing)}"
        )
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    new_puzzle_id = f"puzzle-{secrets.token_hex(8)}"
    saved_puzzle = puzzle.model_copy(update={"puzzleId": new_puzzle_id})
    saved_answers = official_answers.model_copy(
        update={"puzzleId": new_puzzle_id}
    )

    puzzle_repository.save_snapshot(saved_puzzle)
    answer_repository.save(saved_answers)

    return {"puzzleId": new_puzzle_id}
