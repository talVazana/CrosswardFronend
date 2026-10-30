"""Authenticated user profiles.

After Google sign-in a user picks a nickname. The nickname is the display name
shown in rooms and on the scoreboard. Every signed-in email is tracked here, so
GOD can list everyone who has logged in. Profiles survive a restart via Firestore.
"""

from __future__ import annotations

from . import firestore_publisher

NICKNAME_MIN = 2
NICKNAME_MAX = 20

# email -> nickname (None when the user signed in but has no nickname yet)
_PROFILES: dict[str, str | None] = {}


def _normalize_email(email: str | None) -> str:
    return (email or "").strip().casefold()


def record_seen(email: str) -> str:
    """Track a signed-in email without requiring a nickname."""
    normalized = _normalize_email(email)
    if normalized not in _PROFILES:
        _PROFILES[normalized] = None
        firestore_publisher.publish_profile(normalized, "")
    return normalized


def get_nickname(email: str | None) -> str | None:
    return _PROFILES.get(_normalize_email(email))


def set_nickname(email: str, nickname: str) -> str:
    normalized = _normalize_email(email)
    value = (nickname or "").strip()
    if not (NICKNAME_MIN <= len(value) <= NICKNAME_MAX):
        raise ValueError(
            f"Nickname must be {NICKNAME_MIN}-{NICKNAME_MAX} characters"
        )
    _PROFILES[normalized] = value
    firestore_publisher.publish_profile(normalized, value)
    return value


def list_profiles() -> dict[str, str | None]:
    return dict(_PROFILES)


def reset_profiles() -> None:
    _PROFILES.clear()


def restore_profiles(mapping: dict[str, str]) -> None:
    for email, nickname in (mapping or {}).items():
        value = (nickname or "").strip()
        _PROFILES[_normalize_email(email)] = (
            value if NICKNAME_MIN <= len(value) <= NICKNAME_MAX else None
        )
