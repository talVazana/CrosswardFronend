from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .puzzle import Puzzle


class RoomStatus(str, Enum):
    draft = "draft"
    lobby = "lobby"
    active = "active"
    paused = "paused"
    finished = "finished"
    closed = "closed"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Room(BaseModel):
    roomId: str
    title: str
    status: RoomStatus
    puzzleSnapshot: Puzzle
    creatorId: str
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)


class Player(BaseModel):
    roomId: str
    playerId: str
    displayName: str
    color: str
    joinedAt: datetime = Field(default_factory=utc_now)
    role: Literal["player", "admin"]

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        import re
        if not re.fullmatch(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("color must match ^#[0-9A-Fa-f]{6}$")
        return v
