"""Per-room statistics: admin-first solves vs player-first solves.

These are informational tallies. They never change the real game scoring.
A player counts 1 for each clue they solved first (the earliest positive score
event for that clue). The admin counts 1 for each clue the admin solved first.
Approving a pending player submission credits the player, not the admin.
"""

from ..api.routes import rooms as rooms_module
from ..services import admin_solves, scoring_service


def build_statistics(room_id: str) -> dict:
    players = [
        player
        for player in rooms_module.player_repository.list_by_room(room_id)
        if player.role == "player"
    ]
    color_to_player = {player.color: player.playerId for player in players}

    first_counts: dict[str, int] = {}
    for (rid, _clue_id), state in scoring_service._default_service._public_clue_states.items():
        if rid != room_id or not state.solved or not state.firstSolverColor:
            continue
        player_id = color_to_player.get(state.firstSolverColor)
        if player_id is not None:
            first_counts[player_id] = first_counts.get(player_id, 0) + 1

    player_entries = [
        {
            "playerId": player.playerId,
            "displayName": player.displayName,
            "color": player.color,
            "solvedClues": first_counts.get(player.playerId, 0),
        }
        for player in players
    ]
    admin_solved = len(admin_solves.list_by_room(room_id))
    players_total = sum(entry["solvedClues"] for entry in player_entries)

    return {
        "players": player_entries,
        "adminSolvedClues": admin_solved,
        "playersTotal": players_total,
        "adminTotal": admin_solved,
    }
