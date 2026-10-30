"""Google sign-in verification and role resolution.

There is no password and no GOD access key. Every protected endpoint reads the
``Authorization`` header, verifies the Google ID token, and resolves the role
from the verified email address.

Two modes:

- Emulator: when ``FIREBASE_AUTH_EMULATOR_HOST`` is set, tokens are minted by the
  local emulator and are not signed by Google. They are decoded without signature
  verification. This is local development only.
- Production: tokens are verified with ``google.oauth2.id_token.verify_firebase_token``
  against the Firebase project. This fails closed when configuration is missing.
"""

from __future__ import annotations

import os

import jwt
from fastapi import HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from .. import special_users

AUTH_HEADER = "Authorization"


def _project_id() -> str:
    return (
        os.environ.get("FIREBASE_PROJECT_ID")
        or os.environ.get("FIRESTORE_PROJECT_ID")
        or "demo-crossword-arena"
    )


def _emulator_mode() -> bool:
    return bool(os.environ.get("FIREBASE_AUTH_EMULATOR_HOST"))


def verify_token(id_token_str: str) -> dict:
    """Return the decoded claims of a Google ID token. Raises 401 on failure."""
    if _emulator_mode():
        try:
            return jwt.decode(id_token_str, options={"verify_signature": False})
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid token") from exc
    try:
        request = google_requests.Request()
        return google_id_token.verify_firebase_token(
            id_token_str, request, audience=_project_id()
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid Google token") from exc


def email_from_token(token: str) -> str | None:
    decoded = verify_token(token)
    email = decoded.get("email")
    if not email:
        return None
    return email


def require_google_user(request: Request) -> str:
    """Return the verified email, or raise 401 when the header is absent or bad."""
    header = request.headers.get(AUTH_HEADER, "")
    token = header[len("Bearer "):].strip() if header.startswith("Bearer ") else header.strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication")
    email = email_from_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Could not read email from token")
    return email


def require_role(request: Request, role: str) -> str:
    email = require_google_user(request)
    if special_users.website_role_for_email(email) != role:
        raise HTTPException(status_code=403, detail="Forbidden")
    return email


def require_admin(request: Request) -> str:
    return require_role(request, special_users.ADMIN)


def require_god(request: Request) -> str:
    return require_role(request, special_users.GOD)
