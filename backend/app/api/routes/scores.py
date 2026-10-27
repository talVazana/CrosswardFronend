from fastapi import APIRouter, HTTPException

from ...repositories.interfaces import PlayerRepository, RoomRepository, ScoreRepository
from ...services import scoring_service
from . import rooms as rooms_module

router = APIRouter()

room_repository: RoomRepository = rooms_module.room_repository
player_repository: PlayerRepository = rooms_module.player_repository
score_repository: ScoreRepository = scoring_service._default_service._score_repository


@router.get("/rooms/{roomId}/scores")
def get_room_scores(roomId: str):
    if room_repository.get(roomId) is None:
        raise HTTPException(status_code=404, detail="Room not found")

    events = score_repository.list_by_room(roomId)
    players = [
        player
        for player in player_repository.list_by_room(roomId)
        if player.role == "player"
    ]

    totals: dict[str, int] = {}
    for event in events:
        totals[event.playerId] = totals.get(event.playerId, 0) + event.points

    scores = [
        {
            "playerId": player.playerId,
            "displayName": player.displayName,
            "color": player.color,
            "totalPoints": totals.get(player.playerId, 0),
        }
        for player in players
    ]
    scores.sort(key=lambda s: (-s["totalPoints"], s["displayName"]))
    return scores


@router.get("/rooms/{roomId}/statistics")
def get_room_statistics(roomId: str):
    if rooms_module.room_repository.get(roomId) is None:
        raise HTTPException(status_code=404, detail="Room not found")

    from ...services import statistics

    return statistics.build_statistics(roomId)
