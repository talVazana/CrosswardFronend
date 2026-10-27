from datetime import datetime

from pydantic import BaseModel, Field

from .gameplay import utc_now


class PlayerTotal(BaseModel):
    """Lifetime points for one player name across every room."""

    displayName: str
    totalScore: int = Field(default=0, ge=0)
    updatedAt: datetime = Field(default_factory=utc_now)
