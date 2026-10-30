import os

os.environ.setdefault("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")

import jwt
import pytest

from app import special_users
from app.api.routes import rooms as rooms_module
from app.repositories.in_memory import (
    InMemoryAdminSolveRepository,
    InMemoryPlayerIdentityRepository,
    InMemoryPlayerTotalRepository,
)
from app.services import admin_solves, gemini_quota, limits, player_totals, profiles


def make_id_token(email: str) -> str:
    """Build a Google-style ID token for local test use.

    The auth module decodes emulator tokens without signature verification, so a
    self-signed JWT with an email claim is enough for tests.
    """
    return jwt.encode({"email": email}, "test-secret", algorithm="HS256")


@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {make_id_token('shachar383838@gmail.com')}"}


@pytest.fixture
def god_headers():
    return {"Authorization": f"Bearer {make_id_token('tal.vazanas@gmail.com')}"}


@pytest.fixture
def player_headers():
    return {"Authorization": f"Bearer {make_id_token('player@example.com')}"}


@pytest.fixture(autouse=True)
def reset_global_player_state():
    """Keep global identities, lifetime totals, admin solves, and runtime settings isolated."""
    rooms_module.identity_repository = InMemoryPlayerIdentityRepository()
    player_totals.repository = InMemoryPlayerTotalRepository()
    admin_solves.repository = InMemoryAdminSolveRepository()
    special_users.reset_special_users()
    limits.reset_overrides()
    gemini_quota.reset_quota()
    profiles.reset_profiles()
    yield
    rooms_module.identity_repository = InMemoryPlayerIdentityRepository()
    player_totals.repository = InMemoryPlayerTotalRepository()
    admin_solves.repository = InMemoryAdminSolveRepository()
    special_users.reset_special_users()
    limits.reset_overrides()
    gemini_quota.reset_quota()
    profiles.reset_profiles()
