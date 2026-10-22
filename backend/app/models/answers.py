from pydantic import BaseModel


class OfficialAnswers(BaseModel):
    puzzleId: str
    answers: dict[str, str]
