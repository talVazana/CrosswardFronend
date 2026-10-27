from datetime import datetime

from pydantic import BaseModel, Field

from .gameplay import utc_now


class AdminSolve(BaseModel):
    """One clue solved first by the room admin (statistics only)."""

    roomId: str
    clueId: str
    adminId: str
    solvedAt: datetime = Field(default_factory=utc_now)
