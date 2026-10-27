import pytest

from app.api.routes import rooms as rooms_module
from app.repositories.in_memory import (
    InMemoryAdminSolveRepository,
    InMemoryPlayerIdentityRepository,
    InMemoryPlayerTotalRepository,
)
from app.services import admin_solves, player_totals


@pytest.fixture(autouse=True)
def reset_global_player_state():
    """Keep global identities, lifetime totals, and admin solves isolated."""
    rooms_module.identity_repository = InMemoryPlayerIdentityRepository()
    player_totals.repository = InMemoryPlayerTotalRepository()
    admin_solves.repository = InMemoryAdminSolveRepository()
    yield
    rooms_module.identity_repository = InMemoryPlayerIdentityRepository()
    player_totals.repository = InMemoryPlayerTotalRepository()
    admin_solves.repository = InMemoryAdminSolveRepository()
