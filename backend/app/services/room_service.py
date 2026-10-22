from ..models.room import Player, Room
from ..repositories.interfaces import PlayerRepository, RoomRepository


class RoomService:
    def __init__(self, room_repository: RoomRepository, player_repository: PlayerRepository):
        self._room_repository = room_repository
        self._player_repository = player_repository

    def verify_player_in_room(self, room_id: str, player_id: str) -> bool:
        room = self._room_repository.get(room_id)
        if room is None:
            return False
        return self._player_repository.get(room_id, player_id) is not None

    def get_room_public_state(self, room_id: str) -> dict:
        room: Room | None = self._room_repository.get(room_id)
        if room is None:
            raise ValueError("Room not found")
        players: list[Player] = self._player_repository.list_by_room(room_id)
        return {
            "roomId": room.roomId,
            "id": room.roomId,
            "title": room.title,
            "status": room.status.value,
            "players": [
                {
                    "playerId": p.playerId,
                    "id": p.playerId,
                    "displayName": p.displayName,
                    "color": p.color,
                }
                for p in players
            ],
            "participants": [
                {
                    "playerId": p.playerId,
                    "id": p.playerId,
                    "displayName": p.displayName,
                    "color": p.color,
                }
                for p in players
            ],
        }
                for p in players
            ],
        }
