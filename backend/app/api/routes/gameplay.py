from fastapi import APIRouter, HTTPException, Request

from ...models.gameplay import PlayerClueState
from ...repositories.interfaces import AnswerRepository, PlayerClueStateRepository
from ...services import firestore_publisher
from . import admin as admin_module
from . import drafts as drafts_module
from . import rooms as rooms_module
from . import submissions as submissions_module

router = APIRouter()

answer_repository: AnswerRepository = admin_module.answer_repository
player_clue_state_repository: PlayerClueStateRepository = drafts_module.player_clue_state_repository


@router.post("/rooms/{roomId}/clues/{clueId}/reveal")
def reveal_answer(roomId: str, clueId: str, request: Request):
    player_id = submissions_module._resolve_player(request, roomId)

    room = rooms_module.room_repository.get(roomId)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    answers = answer_repository.get(room.puzzleSnapshot.puzzleId)
    official_answer = answers.answers.get(clueId) if answers else None
    if official_answer is None:
        raise HTTPException(status_code=400, detail="Answer not available yet")

    state = player_clue_state_repository.get(roomId, player_id, clueId)
    if state is None:
        state = PlayerClueState(playerId=player_id, clueId=clueId)
    state.revealed = True
    state.solution = official_answer
    player_clue_state_repository.save(state, roomId)
    firestore_publisher.publish_player_state(roomId, state)

    return {"answer": official_answer}
