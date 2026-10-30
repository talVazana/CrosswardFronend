"""Authenticated user profiles.

After Google sign-in a user picks a nickname. The nickname is the display name
shown in rooms and on the scoreboard. Profiles are keyed by the verified email
address and survive a restart via Firestore.
"""

from __future__ import annotations

from . import firestore_publisher

NICKNAME_MIN = 2
NICKNAME_MAX = 20

_PROFILES: dict[str, str] = {}


def _normalize_email(email: str | None) -> str:
    return (email or "").strip().casefold()


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


def list_profiles() -> dict[str, str]:
    return dict(_PROFILES)


def reset_profiles() -> None:
    _PROFILES.clear()


def restore_profiles(mapping: dict[str, str]) -> None:
    for email, nickname in (mapping or {}).items():
        value = (nickname or "").strip()
        if not (NICKNAME_MIN <= len(value) <= NICKNAME_MAX):
            continue
        _PROFILES[_normalize_email(email)] = value
