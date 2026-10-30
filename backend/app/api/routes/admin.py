import secrets
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ...models.answers import OfficialAnswers
from ...models.gameplay import SubmissionStatus
from ...models.room import Player, Room, RoomStatus
from ...repositories.in_memory import InMemoryAnswerRepository
from ...repositories.interfaces import AnswerRepository
from ...services import auth, cookies, firestore_publisher, telegram_notifier
from ...services import scoring_service
from ...services.puzzle_image_processor import PuzzleProcessingError, process_image
from ...services.puzzle_utils import normalize_answer
from ...services.reconciliation_service import reconcile_pending_submissions
from . import events as events_module
from . import rooms as rooms_module

router = APIRouter()

ADMIN_SESSION_COOKIE_NAME = "Admin-Session-Token"

answer_repository: AnswerRepository = InMemoryAnswerRepository()
_admin_auth_tokens: set[str] = set()

_ENDPOINT_TRANSITIONS: dict[str, tuple[frozenset[RoomStatus], RoomStatus]] = {
    "start": (frozenset({RoomStatus.lobby}), RoomStatus.active),
    "pause": (frozenset({RoomStatus.active}), RoomStatus.paused),
    "resume": (frozenset({RoomStatus.paused}), RoomStatus.active),
    "finish": (frozenset({RoomStatus.active, RoomStatus.paused}), RoomStatus.finished),
    "close": (frozenset({RoomStatus.finished}), RoomStatus.closed),
}


class AnswerRequest(BaseModel):
    answer: str


def _resolve_admin(request: Request):
    # A Google ID token is the primary admin credential. Cookie sessions stay
    # supported for older clients, but the token must be checked first so an
    # unrelated player cookie cannot block a valid admin.
    auth_error: HTTPException | None = None
    if request.headers.get(auth.AUTH_HEADER):
        try:
            email = auth.require_admin(request)
            return SimpleNamespace(playerId="admin", displayName=email, role="admin")
        except HTTPException as exc:
            if exc.status_code not in (401, 403):
                raise
            auth_error = exc

    admin_cookie = request.cookies.get(ADMIN_SESSION_COOKIE_NAME)
    if admin_cookie is not None and admin_cookie in _admin_auth_tokens:
        return SimpleNamespace(playerId="admin", displayName="Admin", role="admin")

    tokens: list[str] = []
    if admin_cookie is not None:
        tokens.append(admin_cookie)
    tokens.extend(
        rooms_module.split_session_tokens(
            request.cookies.get(rooms_module.SESSION_COOKIE_NAME)
        )
    )
    header_token = request.headers.get(rooms_module.SESSION_HEADER_NAME)
    if header_token and header_token.strip():
        tokens.append(header_token.strip())
    if not tokens:
        if auth_error is not None:
            raise auth_error
        raise HTTPException(status_code=401, detail="Unauthorized")

    for token in tokens:
        session = rooms_module._sessions.get(token)
        if session is None:
            continue
        player = rooms_module.player_repository.get(session[0], session[1])
        if player is not None and player.role == "admin":
            return player
    if any(token in rooms_module._sessions for token in tokens):
        raise HTTPException(status_code=403, detail="Forbidden")
    if auth_error is not None:
        raise auth_error
    raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/admin/session")
def create_admin_session(request: Request, response: Response):
    email = auth.require_admin(request)
    token = secrets.token_hex(16)
    _admin_auth_tokens.add(token)
    firestore_publisher.publish_admin_token(token)
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE_NAME,
        value=token,
        **cookies.session_cookie_kwargs(),
    )
    return {"roomId": None, "playerId": "admin", "displayName": email}


@router.get("/admin/rooms")
def list_admin_rooms(request: Request):
    _resolve_admin(request)
    return rooms_module.list_room_summaries()


@router.put("/admin/puzzles/{puzzleId}/clues/{clueId}/answer")
def save_official_answer(puzzleId: str, clueId: str, body: AnswerRequest, request: Request):
    admin = _resolve_admin(request)
    answers = answer_repository.get(puzzleId)
    if answers is None:
        answers = OfficialAnswers(puzzleId=puzzleId, answers={})
    official_answer = normalize_answer(body.answer)
    answers.answers[clueId] = official_answer
    answer_repository.save(answers)
    firestore_publisher.publish_answers(puzzleId, answers.answers)

    rooms = rooms_module.room_repository._rooms.values()
    for room in rooms:
        if room.puzzleSnapshot.puzzleId == puzzleId:
            reconcile_pending_submissions(room.roomId, clueId, official_answer)
            from ...services import admin_solves

            admin_solves.record_first_solve(room.roomId, clueId, admin.playerId)
            firestore_publisher.publish_room(room.roomId)

    return {"status": "ok"}


@router.post("/admin/rooms", status_code=201)
async def create_room(request: Request):
    _resolve_admin(request)

    title = request.query_params.get("title") or "New Room"
    image_bytes = await request.body()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image is required")

    try:
        puzzle = process_image(image_bytes)
    except PuzzleProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    from . import admin_puzzles as admin_puzzles_module

    room_id = f"room-{secrets.token_hex(4)}"
    puzzle_id = f"puzzle-{secrets.token_hex(8)}"
    saved_puzzle = puzzle.model_copy(update={"puzzleId": puzzle_id})
    saved_answers = OfficialAnswers(puzzleId=puzzle_id, answers={})

    admin_puzzles_module.puzzle_repository.save_snapshot(saved_puzzle)
    answer_repository.save(saved_answers)

    admin_id = f"admin-{secrets.token_hex(8)}"
    admin_player = Player(
        roomId=room_id,
        playerId=admin_id,
        displayName="Admin",
        color="#FF0000",
        role="admin",
    )
    rooms_module.player_repository.add(admin_player)
    admin_token = secrets.token_hex(16)
    rooms_module._sessions[admin_token] = (room_id, admin_id)
    firestore_publisher.publish_session(admin_token, room_id, admin_id)

    room = Room(
        roomId=room_id,
        title=title,
        status=RoomStatus.lobby,
        puzzleSnapshot=saved_puzzle,
        creatorId=admin_id,
    )
    rooms_module.room_repository.create(room)

    firestore_publisher.publish_room_image(room_id, image_bytes)
    firestore_publisher.publish_room(room_id)

    return {"roomId": room_id, "puzzleId": puzzle_id, "status": room.status.value}


@router.get("/admin/me")
def admin_me(request: Request):
    _resolve_admin(request)
    return {"isAdmin": True}


@router.delete("/admin/rooms/{roomId}")
def delete_room(roomId: str, request: Request):
    _resolve_admin(request)

    room = rooms_module.room_repository.get(roomId)
    puzzle_id = room.puzzleSnapshot.puzzleId if room is not None else None
    removed_tokens = [k for k, v in rooms_module._sessions.items() if v[0] == roomId]
    for token in removed_tokens:
        firestore_publisher.delete_session(token)

    rooms_module.room_repository._rooms.pop(roomId, None)
    rooms_module.player_repository._players = {
        k: v
        for k, v in rooms_module.player_repository._players.items()
        if k[0] != roomId
    }
    scoring_service._default_service._score_repository._events = {
        k: v
        for k, v in scoring_service._default_service._score_repository._events.items()
        if v.roomId != roomId
    }
    scoring_service._default_service._public_clue_states = {
        k: v
        for k, v in scoring_service._default_service._public_clue_states.items()
        if k[0] != roomId
    }
    rooms_module._sessions = {
        k: v for k, v in rooms_module._sessions.items() if v[0] != roomId
    }

    from . import drafts as drafts_module
    from . import submissions as submissions_module

    submissions_module.submission_repository._submissions = {
        k: v
        for k, v in submissions_module.submission_repository._submissions.items()
        if v.roomId != roomId
    }
    from ...services import admin_solves

    admin_solves.remove_room(roomId)
    removed_states = [
        key for key in drafts_module.player_clue_state_repository.states if key[0] == roomId
    ]
    for _, player_id, clue_id in removed_states:
        firestore_publisher.delete_player_state(roomId, player_id, clue_id)
    drafts_module.player_clue_state_repository.states = {
        k: v
        for k, v in drafts_module.player_clue_state_repository.states.items()
        if k[0] != roomId
    }
    firestore_publisher.delete_room_docs(roomId, puzzle_id)

    return {"status": "ok"}


def _admin_transition(roomId: str, action: str, request: Request) -> Room:
    _resolve_admin(request)
    allowed_sources, target = _ENDPOINT_TRANSITIONS[action]
    room = rooms_module.room_repository.get(roomId)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.status not in allowed_sources:
        raise HTTPException(status_code=400, detail=f"Invalid transition from {room.status.value} to {target.value}")
    room.status = target
    rooms_module.room_repository.update(room)
    events_module.broadcast_room_status_changed(roomId, room.status.value)
    firestore_publisher.publish_room(roomId)
    if action == "start":
        telegram_notifier.notify_game_started(room)
    elif action == "finish":
        telegram_notifier.notify_game_finished(room)
    return room


@router.get("/admin/rooms/{roomId}")
def get_admin_room_state(roomId: str, request: Request):
    _resolve_admin(request)
    room = rooms_module.room_repository.get(roomId)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    from . import submissions as submissions_module

    players = [
        player
        for player in rooms_module.player_repository.list_by_room(roomId)
        if player.role == "player"
    ]
    totals: dict[str, int] = {}
    for event in scoring_service._default_service._score_repository.list_by_room(roomId):
        totals[event.playerId] = totals.get(event.playerId, 0) + event.points
    scores = [
        {
            "playerId": player.playerId,
            "displayName": player.displayName,
            "score": totals.get(player.playerId, 0),
        }
        for player in players
    ]
    answers = answer_repository.get(room.puzzleSnapshot.puzzleId)
    from ...services import statistics

    return {
        "roomId": room.roomId,
        "id": room.roomId,
        "title": room.title,
        "status": room.status.value,
        "puzzleId": room.puzzleSnapshot.puzzleId,
        "puzzle": room.puzzleSnapshot.model_dump(),
        "officialAnswers": answers.answers if answers else {},
        "solvedClues": scoring_service._default_service.list_solved_clues(roomId),
        "players": [
            {"id": p.playerId, "displayName": p.displayName, "color": p.color}
            for p in players
        ],
        "pendingSubmissions": [
            {
                "submissionId": s.submissionId,
                "clueId": s.clueId,
                "playerId": s.playerId,
                "answer": s.answer,
            }
            for s in submissions_module.submission_repository.list_pending_by_room(roomId)
        ],
        "scores": scores,
        "statistics": statistics.build_statistics(roomId),
    }


@router.post("/admin/rooms/{roomId}/submissions/{submissionId}/reject")
def reject_submission(roomId: str, submissionId: str, request: Request):
    _resolve_admin(request)

    from . import submissions as submissions_module

    submission = submissions_module.submission_repository.get(submissionId)
    if submission is None or submission.roomId != roomId:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.status is not SubmissionStatus.pending:
        raise HTTPException(status_code=409, detail="Submission already reviewed")

    submissions_module.submission_repository.update_status(
        submissionId, SubmissionStatus.rejected, 0
    )
    firestore_publisher.publish_submission(submission)
    return {
        "status": SubmissionStatus.rejected.value,
        "clueId": submission.clueId,
        "playerId": submission.playerId,
    }


@router.post("/admin/rooms/{roomId}/start")
def start_room(roomId: str, request: Request):
    return _admin_transition(roomId, "start", request)


@router.post("/admin/rooms/{roomId}/pause")
def pause_room(roomId: str, request: Request):
    return _admin_transition(roomId, "pause", request)


@router.post("/admin/rooms/{roomId}/resume")
def resume_room(roomId: str, request: Request):
    return _admin_transition(roomId, "resume", request)


@router.post("/admin/rooms/{roomId}/finish")
def finish_room(roomId: str, request: Request):
    return _admin_transition(roomId, "finish", request)


@router.post("/admin/rooms/{roomId}/close")
def close_room(roomId: str, request: Request):
    return _admin_transition(roomId, "close", request)
