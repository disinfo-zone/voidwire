"""FastAPI dependency injection."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.database import get_session_factory
from voidwire.models import AdminUser, User

USER_AUTH_COOKIE_NAME = "voidwire_user_token"
ADMIN_AUTH_COOKIE_NAME = "voidwire_admin_token"
CSRF_COOKIE_NAME = "voidwire_csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
ROLE_LEVELS = {
    "readonly": 10,
    "support": 20,
    "admin": 30,
    "owner": 40,
}


def _safe_token_version(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0
        try:
            return int(stripped)
        except ValueError:
            return 0
    return 0


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _extract_bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        return token or None
    return None


def _extract_cookie_token(request: Request, cookie_name: str) -> str | None:
    cookie_token = request.cookies.get(cookie_name, "").strip()
    return cookie_token or None


def _decode_token(request: Request, *, cookie_name: str) -> dict:
    """Decode JWT from Authorization header or designated auth cookie."""
    settings = get_settings()
    raw_token = _extract_bearer_token(request) or _extract_cookie_token(request, cookie_name)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    try:
        payload = jwt.decode(raw_token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> AdminUser:
    payload = _decode_token(request, cookie_name=ADMIN_AUTH_COOKIE_NAME)
    if payload.get("type") == "user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = payload.get("sub", "")
    user = await db.get(AdminUser, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    token_version = _safe_token_version(payload.get("tv", 0))
    if _safe_token_version(getattr(user, "token_version", 0)) != token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is no longer valid",
        )
    return user


async def get_current_public_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    payload = _decode_token(request, cookie_name=USER_AUTH_COOKIE_NAME)
    if payload.get("type") != "user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user_id = payload.get("sub", "")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    token_version = _safe_token_version(payload.get("tv", 0))
    if _safe_token_version(getattr(user, "token_version", 0)) != token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is no longer valid",
        )
    return user


async def get_optional_public_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    raw_token = _extract_bearer_token(request) or _extract_cookie_token(
        request, USER_AUTH_COOKIE_NAME
    )
    if not raw_token:
        return None
    try:
        settings = get_settings()
        payload = jwt.decode(raw_token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if payload.get("type") != "user":
        return None
    user_id = payload.get("sub", "")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        return None
    token_version = _safe_token_version(payload.get("tv", 0))
    if _safe_token_version(getattr(user, "token_version", 0)) != token_version:
        return None
    return user


def _required_admin_level(path: str, method: str) -> int:
    method_upper = method.upper()

    if path.startswith("/admin/backup"):
        return ROLE_LEVELS["owner"]
    if path.startswith("/admin/site"):
        return ROLE_LEVELS["owner"]
    if path.startswith("/admin/settings"):
        return ROLE_LEVELS["owner"]
    if path.startswith("/admin/llm"):
        return ROLE_LEVELS["owner"]

    if path.startswith("/admin/accounts"):
        if path.startswith("/admin/accounts/admin-users"):
            if method_upper == "GET":
                return ROLE_LEVELS["admin"]
            return ROLE_LEVELS["owner"]
        if path.startswith("/admin/accounts/discount-codes") and method_upper in {
            "POST",
            "PATCH",
            "DELETE",
        }:
            return ROLE_LEVELS["admin"]
        if path == "/admin/accounts/users" and method_upper == "POST":
            return ROLE_LEVELS["admin"]
        if path.startswith("/admin/accounts/users/") and method_upper in {
            "PATCH",
            "PUT",
            "DELETE",
            "POST",
        }:
            return ROLE_LEVELS["admin"]
        return ROLE_LEVELS["support"]

    if path.startswith("/admin/analytics") or path.startswith("/admin/audit"):
        return ROLE_LEVELS["readonly"]

    if path.startswith("/admin/pipeline"):
        if method_upper == "GET":
            return ROLE_LEVELS["support"]
        return ROLE_LEVELS["admin"]

    if path.startswith("/admin"):
        if method_upper == "GET":
            return ROLE_LEVELS["support"]
        return ROLE_LEVELS["admin"]

    return ROLE_LEVELS["readonly"]


def require_admin(
    request: Request,
    user: AdminUser = Depends(get_current_user),
) -> AdminUser:
    role = str(getattr(user, "role", "owner")).strip().lower() or "owner"
    user_level = ROLE_LEVELS.get(role)
    if user_level is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin role")

    required_level = _required_admin_level(request.url.path, request.method)
    if user_level < required_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role permissions",
        )
    return user
