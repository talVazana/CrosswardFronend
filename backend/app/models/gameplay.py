from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SubmissionStatus(str, Enum):
    pending = "pending"
    correct = "correct"
    incorrect = "incorrect"
    rejected = "rejected"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Submission(BaseModel):
    submissionId: str
    roomId: str
    playerId: str
    clueId: str
    answer: str
    serverTimestamp: datetime = Field(default_factory=utc_now)
    status: SubmissionStatus = SubmissionStatus.pending
    pointsAwarded: int = Field(default=0, ge=0)


class PlayerClueState(BaseModel):
    playerId: str
    clueId: str
    draft: str = ""
    revealed: bool = False
    scored: bool = False
    solution: str = ""


class PublicClueState(BaseModel):
    clueId: str
    solved: bool = False
    firstSolverColor: Optional[str] = None


class ScoreEvent(BaseModel):
    scoreEventId: str
    roomId: str
    playerId: str
    clueId: str
    points: int = Field(ge=0)
    reason: str
    timestamp: datetime = Field(default_factory=utc_now)
