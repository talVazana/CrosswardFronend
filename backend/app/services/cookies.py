"""Cookie settings for cross-origin deployment.

The backend (``*.run.app``) and frontend (``*.hosted.app``) are different
origins. For browser sessions to work across them, cookies must use
``SameSite=None`` and ``Secure``. Set both via environment variables in
production:

- ``COOKIE_SECURE=true``
- ``COOKIE_SAMESITE=none``

Local development keeps the defaults (``secure=false``, ``samesite=lax``).
"""

from __future__ import annotations

import os


def secure() -> bool:
    value = os.environ.get("COOKIE_SECURE", "false").strip().lower()
    return value in ("1", "true", "yes", "on")


def samesite() -> str:
    value = os.environ.get("COOKIE_SAMESITE", "lax").strip().lower()
    return value if value in ("lax", "strict", "none") else "lax"
