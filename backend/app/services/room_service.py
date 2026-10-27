from ..models.room import Player, Room, RoomStatus
from ..repositories.interfaces import PlayerRepository, RoomRepository
from . import scoring_service

_STATUS_ORDER = {
    RoomStatus.active: 0,
    RoomStatus.lobby: 1,
    RoomStatus.paused: 2,
    RoomStatus.draft: 3,
    RoomStatus.finished: 4,
    RoomStatus.closed: 5,
}


class RoomService:
    def __init__(self, room_repository: RoomRepository, player_repository: PlayerRepository):
        self._room_repository = room_repository
        self._player_repository = player_repository

    def verify_player_in_room(self, room_id: str, player_id: str) -> bool:
        room = self._room_repository.get(room_id)
        if room is None:
            return False
        return self._player_repository.get(room_id, player_id) is not None

    def list_room_summaries(self) -> list[dict]:
        rooms = self._room_repository.list_all()
        rooms.sort(
            key=lambda room: (
                _STATUS_ORDER.get(room.status, len(_STATUS_ORDER)),
                room.title.lower(),
                room.roomId,
            )
        )
        return [
            {
                "roomId": room.roomId,
                "id": room.roomId,
                "title": room.title,
                "status": room.status.value,
                "playerCount": len(
                    [
                        player
                        for player in self._player_repository.list_by_room(room.roomId)
                        if player.role == "player"
                    ]
                ),
                "width": room.puzzleSnapshot.width,
                "height": room.puzzleSnapshot.height,
                "clueCount": len(
                    room.puzzleSnapshot.displayClues
                    if room.puzzleSnapshot.displayClues
                    else room.puzzleSnapshot.clues
                ),
            }
            for room in rooms
        ]

    def get_room_public_state(self, room_id: str) -> dict:
        room: Room | None = self._room_repository.get(room_id)
        if room is None:
            raise ValueError("Room not found")
        players: list[Player] = [
            player
            for player in self._player_repository.list_by_room(room_id)
            if player.role == "player"
        ]
        totals: dict[str, int] = {}
        for event in scoring_service._default_service._score_repository.list_by_room(room_id):
            totals[event.playerId] = totals.get(event.playerId, 0) + event.points
        from . import statistics

        return {
            "roomId": room.roomId,
            "id": room.roomId,
            "title": room.title,
            "status": room.status.value,
            "puzzle": room.puzzleSnapshot.model_dump(),
            "solvedClues": scoring_service._default_service.list_solved_clues(room_id),
            "players": [
                {
                    "id": p.playerId,
                    "displayName": p.displayName,
                    "color": p.color,
                }
                for p in players
            ],
            "scores": [
                {
                    "playerId": p.playerId,
                    "displayName": p.displayName,
                    "score": totals.get(p.playerId, 0),
                }
                for p in players
            ],
            "statistics": statistics.build_statistics(room_id),
        }
