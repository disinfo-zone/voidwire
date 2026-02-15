"""Admin authentication endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pyotp
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.models import AdminUser
from voidwire.services.encryption import decrypt_value

from api.dependencies import get_current_user, get_db
from api.middleware.auth import create_access_token, verify_password

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str
    totp_code: str


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
    )


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str | int]:
    result = await db.execute(
        select(AdminUser).where(func.lower(AdminUser.email) == req.email.strip().lower())
    )
    user = result.scalars().first()
    if not user or not user.is_active:
        raise _invalid_credentials()

    if not verify_password(req.password, user.password_hash):
        raise _invalid_credentials()

    if not user.totp_secret:
        raise _invalid_credentials()

    try:
        secret = decrypt_value(user.totp_secret)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt TOTP secret",
        ) from exc

    if not pyotp.TOTP(secret).verify(req.totp_code, valid_window=1):
        raise _invalid_credentials()

    user.last_login_at = datetime.now(UTC)
    settings = get_settings()
    token = create_access_token(
        user_id=str(user.id),
        expires_delta=timedelta(minutes=settings.jwt_expire_minutes),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": settings.jwt_expire_minutes,
    }


@router.get("/me")
async def me(user: AdminUser = Depends(get_current_user)) -> dict[str, str]:
    return {"id": str(user.id), "email": user.email}
