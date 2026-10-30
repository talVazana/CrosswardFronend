"""GOD window backend.

GOD is a website superuser: it manages runtime limits and special users, but it
cannot perform game admin actions. Access requires a verified Google account
whose email has the ``god`` role.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ... import special_users
from ...services import auth, firestore_publisher, gemini_quota, limits

router = APIRouter()

_AUDIT: list[dict[str, Any]] = []
_AUDIT_LIMIT = 50


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: Literal["god", "admin"]


def _require_god(request: Request) -> str:
    return auth.require_god(request)


def _audit(actor: str, action: str, detail: dict[str, Any] | None = None) -> None:
    _AUDIT.append(
        {
            "time": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "detail": detail or {},
        }
    )
    del _AUDIT[:-_AUDIT_LIMIT]


@router.get("/god/me")
def god_me(request: Request):
    _require_god(request)
    return {"isGod": True}


@router.get("/god/settings")
def god_settings(request: Request):
    _require_god(request)
    return {"settings": limits.limit_snapshot()}


@router.put("/god/settings")
def update_god_settings(body: SettingsUpdate, request: Request):
    actor = _require_god(request)
    try:
        limits.set_overrides(body.values)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit(actor, "update_settings", body.values)
    firestore_publisher.publish_god_settings(limits.current_overrides())
    return {"settings": limits.limit_snapshot()}


@router.post("/god/settings/reset")
def reset_god_settings(request: Request):
    actor = _require_god(request)
    limits.reset_overrides()
    _audit(actor, "reset_settings")
    firestore_publisher.publish_god_settings(limits.current_overrides())
    return {"settings": limits.limit_snapshot()}


@router.get("/god/users")
def god_users(request: Request):
    _require_god(request)
    users = [
        {"email": email, "role": role}
        for email, role in sorted(special_users.list_special_users().items())
    ]
    return {"users": users}


@router.post("/god/users", status_code=201)
def add_god_user(body: UserCreate, request: Request):
    actor = _require_god(request)
    try:
        special_users.add_special_user(body.email, body.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit(actor, "add_user", {"email": body.email, "role": body.role})
    firestore_publisher.publish_special_users(special_users.list_special_users())
    return {"email": special_users.normalize_email(body.email), "role": body.role}


@router.delete("/god/users/{email}")
def remove_god_user(email: str, request: Request):
    actor = _require_god(request)
    try:
        removed = special_users.remove_special_user(email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not removed:
        raise HTTPException(status_code=404, detail="User not found")
    _audit(actor, "remove_user", {"email": special_users.normalize_email(email)})
    firestore_publisher.publish_special_users(special_users.list_special_users())
    return {"status": "ok"}


@router.get("/god/status")
def god_status(request: Request):
    _require_god(request)
    return {
        "authMode": "emulator" if auth._emulator_mode() else "google",
        "geminiConfigured": bool(
            os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        ),
        "telegramConfigured": bool(
            os.environ.get("TELEGRAM_BOT_TOKEN")
            and os.environ.get("TELEGRAM_CHAT_ID")
        ),
        "specialUsers": len(special_users.list_special_users()),
        "overriddenSettings": len(limits.current_overrides()),
        "geminiUsage": gemini_quota.usage(),
        "audit": list(reversed(_AUDIT[-20:])),
    }


@router.post("/god/quota/reset")
def reset_gemini_quota(request: Request):
    actor = _require_god(request)
    gemini_quota.reset_quota()
    _audit(actor, "reset_quota")
    return {"geminiUsage": gemini_quota.usage()}
