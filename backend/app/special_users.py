"""Privileged website accounts.

Authentication is not configured yet. This module is the single source of
truth for the special website users. It is intentionally kept on the server:
the GOD account must never be exposed to the browser or to other users.

Roles
-----
``god``
    Website superuser. Can add and remove users and change runtime limits.
    Cannot perform game admin actions. While playing, acts as a regular player.

``admin``
    Website admin with every game admin role.
"""

from __future__ import annotations

from typing import Literal

WebsiteRole = Literal["god", "admin"]

GOD: WebsiteRole = "god"
ADMIN: WebsiteRole = "admin"

GOD_EMAIL = "tal.vazanas@gmail.com"
ADMIN_EMAIL = "shachar383838@gmail.com"

DEFAULT_SPECIAL_USERS: dict[str, WebsiteRole] = {
    GOD_EMAIL: GOD,
    ADMIN_EMAIL: ADMIN,
}

SPECIAL_USERS: dict[str, WebsiteRole] = dict(DEFAULT_SPECIAL_USERS)


def normalize_email(email: str | None) -> str:
    """Return a comparable form of an email address."""
    return (email or "").strip().casefold()


def list_special_users() -> dict[str, WebsiteRole]:
    return dict(SPECIAL_USERS)


def website_role_for_email(email: str | None) -> WebsiteRole | None:
    """Return the website role for an email, or None for everyone else."""
    return SPECIAL_USERS.get(normalize_email(email))


def is_god(email: str | None) -> bool:
    """True when the email belongs to the website superuser."""
    return website_role_for_email(email) == GOD


def has_game_admin_role(email: str | None) -> bool:
    """True when the email may perform game admin actions."""
    return website_role_for_email(email) == ADMIN


def add_special_user(email: str, role: str) -> WebsiteRole:
    normalized = normalize_email(email)
    if not normalized or "@" not in normalized:
        raise ValueError("A valid email is required")
    if role not in (GOD, ADMIN):
        raise ValueError("Role must be 'god' or 'admin'")
    if normalized == normalize_email(GOD_EMAIL) and role != GOD:
        raise ValueError("The primary GOD account cannot be demoted")
    SPECIAL_USERS[normalized] = role  # type: ignore[assignment]
    return role  # type: ignore[return-value]


def remove_special_user(email: str) -> bool:
    normalized = normalize_email(email)
    if normalized == normalize_email(GOD_EMAIL):
        raise ValueError("The primary GOD account cannot be removed")
    return SPECIAL_USERS.pop(normalized, None) is not None


def reset_special_users() -> None:
    SPECIAL_USERS.clear()
    SPECIAL_USERS.update(DEFAULT_SPECIAL_USERS)


def restore_special_users(mapping: dict[str, str]) -> None:
    """Apply a saved special-user map, keeping the primary GOD account."""
    restored: dict[str, WebsiteRole] = dict(DEFAULT_SPECIAL_USERS)
    for email, role in (mapping or {}).items():
        if role not in (GOD, ADMIN):
            continue
        normalized = normalize_email(email)
        if "@" not in normalized:
            continue
        if normalized == normalize_email(GOD_EMAIL):
            continue
        restored[normalized] = role  # type: ignore[assignment]
    SPECIAL_USERS.clear()
    SPECIAL_USERS.update(restored)
