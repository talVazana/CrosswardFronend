"""Cookie settings shared by player and admin sessions.

The App Hosting frontend (*.hosted.app) and the Cloud Run API (*.run.app) are
different sites, so production session cookies must be ``Secure`` and
``SameSite=None`` for browsers to send them with cross-site requests. Local
development keeps ``Lax``/non-secure so plain http://localhost works.
"""

from __future__ import annotations

import os


def _production() -> bool:
    return os.environ.get("FIRESTORE_MODE", "").strip().lower() == "production"


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def secure_cookies() -> bool:
    return _bool_env("COOKIE_SECURE", _production())


def cookie_samesite() -> str:
    value = os.environ.get("COOKIE_SAMESITE", "").strip().lower()
    if value in {"lax", "strict", "none"}:
        return value
    return "none" if _production() else "lax"


def session_cookie_kwargs() -> dict:
    """Attributes for the player and admin session cookies."""
    return {
        "httponly": True,
        "secure": secure_cookies(),
        "samesite": cookie_samesite(),
        "path": "/",
    }
