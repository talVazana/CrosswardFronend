"""Authenticated user profile endpoints.

A signed-in user sets a nickname once. The nickname becomes the display name in
rooms. Access requires a verified Google token in the ``Authorization`` header.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ...services import auth, profiles

router = APIRouter()


class ProfileUpdate(BaseModel):
    nickname: str = Field(min_length=profiles.NICKNAME_MIN, max_length=profiles.NICKNAME_MAX)


@router.get("/me/profile")
def get_profile(request: Request):
    email = auth.require_google_user(request)
    return {
        "email": email,
        "nickname": profiles.get_nickname(email),
    }


@router.put("/me/profile")
def set_profile(body: ProfileUpdate, request: Request):
    email = auth.require_google_user(request)
    try:
        nickname = profiles.set_nickname(email, body.nickname)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"email": email, "nickname": nickname}
