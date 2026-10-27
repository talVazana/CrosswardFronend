from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ...models.gameplay import PlayerClueState, Submission, SubmissionStatus
from ...models.room import RoomStatus
from ...repositories.in_memory import InMemoryPlayerClueStateRepository
from ...repositories.interfaces import PlayerClueStateRepository
from ...services import firestore_publisher
from . import rooms as rooms_module

router = APIRouter()

player_clue_state_repository: PlayerClueStateRepository = InMemoryPlayerClueStateRepository()
_player_clue_states = player_clue_state_repository.states


class DraftRequest(BaseModel):
    draft: str = Field(max_length=100)


def _resolve_player(request: Request, room_id: str) -> str:
    session_token = request.cookies.get(rooms_module.SESSION_COOKIE_NAME)
    if session_token is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    session = rooms_module.get_room_session(session_token, room_id)
    if session is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    _, player_id = session
    if rooms_module.player_repository.get(room_id, player_id) is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return player_id


def _validate_request_identity(request: Request, room_id: str, player_id: str) -> None:
    cookie_token = request.cookies.get(rooms_module.SESSION_COOKIE_NAME)
    if cookie_token is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    session = rooms_module.get_room_session(cookie_token, room_id)
    if session is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    session_room_id, session_player_id = session
    if session_room_id != room_id or session_player_id != player_id:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.put("/rooms/{roomId}/clues/{clueId}/draft")
def save_draft(roomId: str, clueId: str, body: DraftRequest, request: Request):
    player_id = _resolve_player(request, roomId)
    _validate_request_identity(request, roomId, player_id)
    room = rooms_module.room_repository.get(roomId)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.status not in (RoomStatus.lobby, RoomStatus.active, RoomStatus.paused):
        raise HTTPException(status_code=400, detail="Drafts are currently disabled")
    state = player_clue_state_repository.get(roomId, player_id, clueId)
    if state is None:
        state = PlayerClueState(playerId=player_id, clueId=clueId)
    state.draft = body.draft
    player_clue_state_repository.save(state, roomId)
    firestore_publisher.publish_player_state(roomId, state)
    return {"status": "ok"}


@router.get("/rooms/{roomId}/drafts")
def get_drafts(roomId: str, request: Request):
    player_id = _resolve_player(request, roomId)
    _validate_request_identity(request, roomId, player_id)
    return {
        state.clueId: state.draft
        for state in player_clue_state_repository.list_by_player(roomId, player_id)
    }


def mark_clue_scored(
    room_id: str, player_id: str, clue_id: str, solution: str = ""
) -> None:
    state = player_clue_state_repository.get(room_id, player_id, clue_id)
    if state is None:
        state = PlayerClueState(playerId=player_id, clueId=clue_id)
    state.scored = True
    if solution:
        state.solution = solution
    player_clue_state_repository.save(state, room_id)
    firestore_publisher.publish_player_state(room_id, state)


@router.get("/rooms/{roomId}/player-progress")
def get_player_progress(roomId: str, request: Request):
    player_id = _resolve_player(request, roomId)
    _validate_request_identity(request, roomId, player_id)
    states = player_clue_state_repository.list_by_player(roomId, player_id)

    from . import submissions as submissions_module

    latest: dict[str, Submission] = {}
    for submission in submissions_module.submission_repository.list_by_player(
        roomId, player_id
    ):
        current = latest.get(submission.clueId)
        if current is None or submission.serverTimestamp >= current.serverTimestamp:
            latest[submission.clueId] = submission

    return {
        "solved": sorted(state.clueId for state in states if state.scored),
        "revealed": sorted(state.clueId for state in states if state.revealed),
        "answers": {
            state.clueId: state.solution
            for state in states
            if state.solution and (state.scored or state.revealed)
        },
        "rejected": [
            {"clueId": clue_id, "submissionId": submission.submissionId}
            for clue_id, submission in sorted(latest.items())
            if submission.status is SubmissionStatus.rejected
        ],
    }
