from fastapi import APIRouter

from ...services import player_totals

router = APIRouter()

LEADERBOARD_LIMIT = 20


@router.get("/players/totals")
def list_player_totals():
    """Return the lifetime score leaderboard for the main screen."""
    return {"players": player_totals.leaderboard()[:LEADERBOARD_LIMIT]}


@router.get("/players/{displayName}/total")
def get_player_total(displayName: str):
    """Return one player's lifetime score by display name."""
    return {
        "displayName": displayName,
        "totalScore": player_totals.get_total(displayName),
    }
