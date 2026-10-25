from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class Cell(BaseModel):
    row: int = Field(ge=0)
    col: int = Field(ge=0)
    type: Literal["white", "black"]
    number: Optional[int] = Field(default=None, ge=1)
    startsAcross: bool
    startsDown: bool


class Clue(BaseModel):
    clueId: str
    number: int = Field(ge=1)
    direction: Literal["across", "down"]
    text: str
    answerLength: int = Field(ge=1)


class Puzzle(BaseModel):
    puzzleId: str
    title: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    cells: list[Cell] = Field(min_length=1)
    clues: list[Clue] = Field(min_length=1)
    displayClues: Optional[list[Clue]] = None

    @model_validator(mode="after")
    def validate_cell_bounds(self):
        for cell in self.cells:
            if not (0 <= cell.row < self.height) or not (0 <= cell.col < self.width):
                raise ValueError(
                    f"Cell ({cell.row}, {cell.col}) is out of bounds for "
                    f"{self.height}x{self.width} puzzle"
                )
        return self
