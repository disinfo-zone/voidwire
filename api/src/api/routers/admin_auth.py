"""Admin authentication endpoints."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.models import AdminUser
from voidwire.services.encryption import decrypt_value

from api.dependencies import (
    ADMIN_AUTH_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    get_current_user,
    get_db,
)
from api.middleware.auth import create_access_token, verify_password
from api.services.auth_lockout import (
    clear_login_failures,
    is_login_blocked,
    record_login_failure,
)

router = APIRouter()
ADMIN_AUTH_COOKIE_PATH = "/"


class LoginRequest(BaseModel):
    email: str
    password: str
    totp_code: str


def _cookie_secure(request: Request) -> bool:
    settings = get_settings()
    if request.url.scheme == "https":
        return True
    return settings.admin_url.lower().startswith("https://")


def _issue_admin_auth_response(
    *,
    user: AdminUser,
    admin_id: str,
    request: Request,
    expires_in_minutes: int,
) -> JSONResponse:
    token_version = getattr(user, "token_version", 0)
    if token_version is None:
        token_version = 0
    token = create_access_token(
        user_id=admin_id,
        expires_delta=timedelta(minutes=expires_in_minutes),
        token_version=token_version,
    )
    response = JSONResponse(
        {
            "detail": "Logged in",
            "token_type": "cookie",
            "expires_in_minutes": expires_in_minutes,
        }
    )
    response.set_cookie(
        key=ADMIN_AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_cookie_secure(request),
        samesite="lax",
        max_age=expires_in_minutes * 60,
        path=ADMIN_AUTH_COOKIE_PATH,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=secrets.token_urlsafe(32),
        httponly=False,
        secure=_cookie_secure(request),
        samesite="lax",
        max_age=expires_in_minutes * 60,
        path=ADMIN_AUTH_COOKIE_PATH,
    )
    return response


def _clear_admin_auth_cookie(response: JSONResponse) -> None:
    response.delete_cookie(
        key=ADMIN_AUTH_COOKIE_NAME,
        path=ADMIN_AUTH_COOKIE_PATH,
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path=ADMIN_AUTH_COOKIE_PATH,
    )


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
    )


def _client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@router.post("/login")
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    normalized_email = req.email.strip().lower()
    identifier = f"{_client_ip(request)}:{normalized_email}"
    blocked, retry_after = await is_login_blocked("admin_login", identifier)
    if blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again in {retry_after} seconds.",
        )

    result = await db.execute(
        select(AdminUser).where(func.lower(AdminUser.email) == normalized_email)
    )
    user = result.scalars().first()
    if not user or not user.is_active:
        await record_login_failure("admin_login", identifier)
        raise _invalid_credentials()

    if not verify_password(req.password, user.password_hash):
        await record_login_failure("admin_login", identifier)
        raise _invalid_credentials()

    if not user.totp_secret:
        await record_login_failure("admin_login", identifier)
        raise _invalid_credentials()

    try:
        secret = decrypt_value(user.totp_secret)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt TOTP secret",
        ) from exc

    if not pyotp.TOTP(secret).verify(req.totp_code, valid_window=1):
        await record_login_failure("admin_login", identifier)
        raise _invalid_credentials()

    await clear_login_failures("admin_login", identifier)
    user.last_login_at = datetime.now(UTC)
    settings = get_settings()
    return _issue_admin_auth_response(
        admin_id=str(user.id),
        user=user,
        request=request,
        expires_in_minutes=settings.jwt_expire_minutes,
    )


@router.get("/me")
async def me(user: AdminUser = Depends(get_current_user)) -> dict[str, str]:
    return {
        "id": str(user.id),
        "email": user.email,
        "role": str(getattr(user, "role", "owner") or "owner"),
    }


@router.post("/logout")
async def logout() -> JSONResponse:
    response = JSONResponse({"detail": "Logged out"})
    _clear_admin_auth_cookie(response)
    return response
