from fastapi import APIRouter

from ...repositories.in_memory import InMemoryPuzzleRepository
from ...repositories.interfaces import AnswerRepository, PuzzleRepository
from . import admin as admin_module

router = APIRouter()

puzzle_repository: PuzzleRepository = InMemoryPuzzleRepository()
answer_repository: AnswerRepository = admin_module.answer_repository
