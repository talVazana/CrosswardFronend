import pytest

from app.api.routes import rooms as rooms_module
from app.repositories.in_memory import (
    InMemoryPlayerIdentityRepository,
    InMemoryPlayerTotalRepository,
)
from app.services import player_totals


@pytest.fixture(autouse=True)
def reset_global_player_state():
    """Keep global identities and lifetime totals isolated between tests."""
    rooms_module.identity_repository = InMemoryPlayerIdentityRepository()
    player_totals.repository = InMemoryPlayerTotalRepository()
    yield
    rooms_module.identity_repository = InMemoryPlayerIdentityRepository()
    player_totals.repository = InMemoryPlayerTotalRepository()
