"""User authentication endpoints."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import Settings, get_settings
from voidwire.models import (
    AnalyticsEvent,
    EmailVerificationToken,
    PasswordResetToken,
    PersonalReading,
    Subscription,
    User,
)

from api.dependencies import CSRF_COOKIE_NAME, get_current_public_user, get_db
from api.middleware.auth import (
    create_access_token,
    hash_password,
    verify_password,
)
from api.services.auth_lockout import (
    clear_login_failures,
    is_login_blocked,
    record_login_failure,
)
from api.services.email_template_service import load_rendered_email_template
from api.services.email_service import send_transactional_email
from api.services.oauth_config import (
    load_public_oauth_providers,
    resolve_oauth_runtime_config,
)
from api.services.site_config import load_site_config

logger = logging.getLogger(__name__)
router = APIRouter()
USER_AUTH_COOKIE_NAME = "voidwire_user_token"
USER_AUTH_COOKIE_PATH = "/"


# --- Request / Response schemas ---


def _validated_email(value: str) -> str:
    normalized = value.strip().lower()
    local, sep, domain = normalized.partition("@")
    if not sep or not local or "." not in domain or domain.endswith("."):
        raise ValueError("Invalid email address")
    return normalized


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(max_length=256)
    display_name: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validated_email(value)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validated_email(value)


class OAuthGoogleRequest(BaseModel):
    id_token: str = Field(min_length=1, max_length=8192)


class OAuthAppleRequest(BaseModel):
    authorization_code: str = Field(min_length=1, max_length=4096)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validated_email(value)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(max_length=256)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class ResendVerificationByEmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validated_email(value)


class UpdateDisplayNameRequest(BaseModel):
    display_name: str = Field(max_length=120)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


class ChangeEmailRequest(BaseModel):
    new_email: str = Field(min_length=3, max_length=320)
    current_password: str | None = Field(default=None, max_length=256)

    @field_validator("new_email")
    @classmethod
    def validate_new_email(cls, value: str) -> str:
        return _validated_email(value)


class DeleteAccountRequest(BaseModel):
    password: str | None = Field(default=None, max_length=256)


def _is_test_user_account(user: User) -> bool:
    return bool(getattr(user, "is_test_user", False))


# --- Helpers ---


def _create_user_token(user: User) -> dict:
    settings = get_settings()
    token_version = getattr(user, "token_version", 0)
    if token_version is None:
        token_version = 0
    token = create_access_token(
        user_id=str(user.id),
        expires_delta=timedelta(minutes=settings.user_jwt_expire_minutes),
        token_type="user",
        token_version=token_version,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": settings.user_jwt_expire_minutes,
    }


def _cookie_secure(request: Request, settings: Settings) -> bool:
    # Prefer runtime request scheme but fall back to configured public site URL
    # for proxy deployments that terminate TLS upstream.
    if request.url.scheme == "https":
        return True
    return settings.site_url.lower().startswith("https://")


def _issue_user_auth_response(user: User, request: Request) -> JSONResponse:
    settings = get_settings()
    payload = _create_user_token(user)
    response = JSONResponse(payload)
    secure = _cookie_secure(request, settings)
    response.set_cookie(
        key=USER_AUTH_COOKIE_NAME,
        value=payload["access_token"],
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.user_jwt_expire_minutes * 60,
        path=USER_AUTH_COOKIE_PATH,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=secrets.token_urlsafe(32),
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=settings.user_jwt_expire_minutes * 60,
        path=USER_AUTH_COOKIE_PATH,
    )
    return response


def _clear_user_auth_cookie(response: JSONResponse) -> None:
    response.delete_cookie(
        key=USER_AUTH_COOKIE_NAME,
        path=USER_AUTH_COOKIE_PATH,
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path=USER_AUTH_COOKIE_PATH,
    )


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _token_fingerprint(raw: str) -> str:
    # Log a short fingerprint only; never log raw token material.
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def _prune_token_tables(db: AsyncSession) -> None:
    now = datetime.now(UTC)
    email_deleted = (
        await db.execute(
            delete(EmailVerificationToken).where(
                (EmailVerificationToken.expires_at <= now)
                | (EmailVerificationToken.used_at.is_not(None))
            )
        )
    ).rowcount or 0
    password_deleted = (
        await db.execute(
            delete(PasswordResetToken).where(
                (PasswordResetToken.expires_at <= now) | (PasswordResetToken.used_at.is_not(None))
            )
        )
    ).rowcount or 0
    db.add(
        AnalyticsEvent(
            event_type="auth.token_cleanup",
            metadata_json={
                "email_tokens_deleted": email_deleted,
                "password_tokens_deleted": password_deleted,
            },
        )
    )


async def _generate_verification_token(user_id, db: AsyncSession) -> str:
    await _prune_token_tables(db)

    # Invalidate old unused verification tokens before issuing a new one.
    await db.execute(
        delete(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.used_at.is_(None),
        )
    )

    raw = secrets.token_hex(32)
    token = EmailVerificationToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(token)
    await db.flush()
    logger.info(
        "Created verification token for user %s (fingerprint=%s; email dispatch pending)",
        user_id,
        _token_fingerprint(raw),
    )
    return raw


async def _public_base_url(db: AsyncSession) -> str:
    settings = get_settings()
    try:
        site_config = await load_site_config(db)
        candidate = str(site_config.get("site_url", "")).strip()
        if candidate:
            return candidate.rstrip("/")
    except Exception:
        logger.warning("Failed loading site config for email links; falling back to SITE_URL")
    return settings.site_url.rstrip("/")


async def _send_verification_email(db: AsyncSession, user: User, raw_token: str) -> bool:
    base_url = await _public_base_url(db)
    verify_link = f"{base_url}/verify-email?token={quote(raw_token)}"
    subject, text_body, html_body = await load_rendered_email_template(
        db,
        template_key="verification",
        context={
            "site_name": "Voidwire",
            "verify_link": verify_link,
            "token": raw_token,
        },
    )
    delivered = await send_transactional_email(
        db,
        to_email=user.email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )
    if not delivered:
        logger.warning(
            "Verification email not sent for user %s (fingerprint=%s)",
            user.id,
            _token_fingerprint(raw_token),
        )
    return delivered


async def _send_password_reset_email(db: AsyncSession, user: User, raw_token: str) -> None:
    base_url = await _public_base_url(db)
    reset_link = f"{base_url}/login?reset_token={quote(raw_token)}"
    subject, text_body, html_body = await load_rendered_email_template(
        db,
        template_key="password_reset",
        context={
            "site_name": "Voidwire",
            "reset_link": reset_link,
            "token": raw_token,
        },
    )
    delivered = await send_transactional_email(
        db,
        to_email=user.email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )
    if not delivered:
        logger.warning(
            "Password reset email not sent for user %s (fingerprint=%s)",
            user.id,
            _token_fingerprint(raw_token),
        )


# --- Endpoints ---


@router.post("/register")
async def register(
    req: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    normalized_email = _normalize_email(req.email)
    existing = await db.execute(select(User).where(func.lower(User.email) == normalized_email))
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Email already registered")

    display_name = (req.display_name or "").strip() or None
    user = User(
        email=normalized_email,
        password_hash=hash_password(req.password),
        display_name=display_name,
        email_verified=False,
    )
    db.add(user)
    await db.flush()

    raw_token = await _generate_verification_token(user.id, db)
    await _send_verification_email(db, user, raw_token)

    return _issue_user_auth_response(user, request)


@router.post("/login")
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    normalized_email = _normalize_email(req.email)
    identifier = f"{_client_ip(request)}:{normalized_email}"
    blocked, retry_after = await is_login_blocked("user_login", identifier)
    if blocked:
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Try again in {retry_after} seconds.",
        )
    result = await db.execute(select(User).where(func.lower(User.email) == normalized_email))
    user = result.scalars().first()
    if not user or not user.is_active or not user.password_hash:
        await record_login_failure("user_login", identifier)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(req.password, user.password_hash):
        await record_login_failure("user_login", identifier)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    await clear_login_failures("user_login", identifier)
    user.last_login_at = datetime.now(UTC)
    return _issue_user_auth_response(user, request)


@router.get("/oauth/providers")
async def oauth_provider_status(db: AsyncSession = Depends(get_db)):
    return await load_public_oauth_providers(db)


@router.post("/oauth/google")
async def oauth_google(
    req: OAuthGoogleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    oauth = await resolve_oauth_runtime_config(db)
    google = oauth.get("google", {})
    if not bool(google.get("enabled")):
        raise HTTPException(status_code=501, detail="Google OAuth not configured")
    google_client_id = str(google.get("client_id", "")).strip()
    if not google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token

        idinfo = google_id_token.verify_oauth2_token(
            req.id_token,
            google_requests.Request(),
            google_client_id,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    google_sub = str(idinfo.get("sub", "")).strip()
    if not google_sub:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    email = _normalize_email(idinfo.get("email", ""))
    email_verified = _coerce_bool(idinfo.get("email_verified"))

    # Find by google_id
    result = await db.execute(select(User).where(User.google_id == google_sub))
    user = result.scalars().first()

    if not user and email:
        if not email_verified:
            raise HTTPException(status_code=401, detail="Google account email must be verified")
        # Check if email already exists (link accounts)
        result = await db.execute(select(User).where(func.lower(User.email) == email))
        user = result.scalars().first()
        if user:
            user.google_id = google_sub
            user.email_verified = bool(user.email_verified or email_verified)

    if not user:
        if not email:
            raise HTTPException(
                status_code=400,
                detail="Google account email is required to create a user",
            )
        if not email_verified:
            raise HTTPException(status_code=401, detail="Google account email must be verified")
        user = User(
            email=email,
            google_id=google_sub,
            display_name=idinfo.get("name"),
            email_verified=True,
        )
        db.add(user)
        await db.flush()

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")

    user.last_login_at = datetime.now(UTC)
    return _issue_user_auth_response(user, request)


@router.post("/oauth/apple")
async def oauth_apple(
    req: OAuthAppleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    oauth = await resolve_oauth_runtime_config(db)
    apple = oauth.get("apple", {})
    if not bool(apple.get("enabled")):
        raise HTTPException(status_code=501, detail="Apple OAuth not configured")

    apple_client_id = str(apple.get("client_id", "")).strip()
    apple_team_id = str(apple.get("team_id", "")).strip()
    apple_key_id = str(apple.get("key_id", "")).strip()
    apple_private_key = str(apple.get("private_key", "")).strip()
    if not apple_client_id:
        raise HTTPException(status_code=501, detail="Apple OAuth not configured")
    if not apple_team_id or not apple_key_id or not apple_private_key:
        raise HTTPException(status_code=501, detail="Apple OAuth is partially configured")

    try:
        import httpx
        from jose import jwt as jose_jwt

        # Exchange authorization_code for id_token via Apple's token endpoint
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://appleid.apple.com/auth/token",
                data={
                    "client_id": apple_client_id,
                    "client_secret": _generate_apple_client_secret(
                        team_id=apple_team_id,
                        client_id=apple_client_id,
                        key_id=apple_key_id,
                        private_key=apple_private_key,
                    ),
                    "code": req.authorization_code,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            token_data = resp.json()

        # Fetch Apple's JWKS and verify
        async with httpx.AsyncClient(timeout=10.0) as client:
            jwks_resp = await client.get("https://appleid.apple.com/auth/keys")
            jwks = jwks_resp.json()

        apple_id_token = str(token_data["id_token"])
        apple_access_token = str(token_data.get("access_token", ""))
        header = jose_jwt.get_unverified_header(apple_id_token)
        # Find matching key
        key = next(k for k in jwks["keys"] if k["kid"] == header["kid"])
        from jose import jwk as jose_jwk

        public_key = jose_jwk.construct(key, algorithm="RS256")

        claims = jose_jwt.decode(
            apple_id_token,
            public_key,
            algorithms=["RS256"],
            audience=apple_client_id,
            issuer="https://appleid.apple.com",
            access_token=apple_access_token,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Apple token")

    apple_sub = str(claims.get("sub", "")).strip()
    if not apple_sub:
        raise HTTPException(status_code=401, detail="Invalid Apple token")
    email = _normalize_email(claims.get("email", ""))
    email_verified = _coerce_bool(claims.get("email_verified"))

    result = await db.execute(select(User).where(User.apple_id == apple_sub))
    user = result.scalars().first()

    if not user and email:
        if not email_verified:
            raise HTTPException(status_code=401, detail="Apple account email must be verified")
        result = await db.execute(select(User).where(func.lower(User.email) == email))
        user = result.scalars().first()
        if user:
            user.apple_id = apple_sub
            user.email_verified = bool(user.email_verified or email_verified)

    if not user:
        if not email:
            raise HTTPException(
                status_code=400,
                detail="Apple account email is required to create a user",
            )
        if not email_verified:
            raise HTTPException(status_code=401, detail="Apple account email must be verified")
        user = User(
            email=email,
            apple_id=apple_sub,
            email_verified=True,
        )
        db.add(user)
        await db.flush()

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")

    user.last_login_at = datetime.now(UTC)
    return _issue_user_auth_response(user, request)


def _generate_apple_client_secret(
    *,
    team_id: str,
    client_id: str,
    key_id: str,
    private_key: str,
) -> str:
    """Generate a short-lived JWT client secret for Apple Sign In."""
    import time

    from jose import jwt as jose_jwt

    now = int(time.time())
    claims = {
        "iss": team_id,
        "iat": now,
        "exp": now + 86400 * 180,
        "aud": "https://appleid.apple.com",
        "sub": client_id,
    }
    headers = {"kid": key_id, "alg": "ES256"}
    return jose_jwt.encode(claims, private_key, algorithm="ES256", headers=headers)


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    await _prune_token_tables(db)

    # Always return 200 to avoid email enumeration
    normalized_email = _normalize_email(req.email)
    result = await db.execute(select(User).where(func.lower(User.email) == normalized_email))
    user = result.scalars().first()

    if user and user.is_active:
        await db.execute(
            delete(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
        )
        raw = secrets.token_hex(32)
        token = PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        db.add(token)
        await db.flush()
        await _send_password_reset_email(db, user, raw)

    return {"detail": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    token_hash = _hash_token(req.token)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.now(UTC),
        )
    )
    token_record = result.scalars().first()
    if not token_record:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = await db.get(User, token_record.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user.password_hash = hash_password(req.new_password)
    user.token_version = int(user.token_version or 0) + 1
    token_record.used_at = datetime.now(UTC)

    return {"detail": "Password reset successfully"}


@router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    token_hash = _hash_token(req.token)
    result = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.expires_at > datetime.now(UTC),
        )
    )
    token_record = result.scalars().first()
    if not token_record:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = await db.get(User, token_record.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user.email_verified = True
    token_record.used_at = datetime.now(UTC)

    return {"detail": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification(
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    if user.email_verified:
        return {"detail": "Email already verified"}

    raw_token = await _generate_verification_token(user.id, db)
    await _send_verification_email(db, user, raw_token)
    return {"detail": "Verification email sent"}


@router.post("/resend-verification/by-email")
async def resend_verification_by_email(
    req: ResendVerificationByEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    normalized_email = _normalize_email(req.email)
    result = await db.execute(select(User).where(func.lower(User.email) == normalized_email))
    user = result.scalars().first()
    if user and user.is_active and not user.email_verified:
        raw_token = await _generate_verification_token(user.id, db)
        await _send_verification_email(db, user, raw_token)
    return {"detail": "If your account exists and is unverified, a verification email has been sent."}


@router.post("/logout")
async def logout() -> JSONResponse:
    response = JSONResponse({"detail": "Logged out"})
    _clear_user_auth_cookie(response)
    return response


@router.post("/logout-all")
async def logout_all_sessions(
    user: User = Depends(get_current_public_user),
) -> JSONResponse:
    user.token_version = int(user.token_version or 0) + 1
    response = JSONResponse({"detail": "All sessions revoked"})
    _clear_user_auth_cookie(response)
    return response


@router.get("/me")
async def me(
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.subscription_service import get_user_tier

    tier = await get_user_tier(user, db)
    is_admin_user = bool(getattr(user, "is_admin_user", False))
    is_test_user = _is_test_user_account(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "email_verified": user.email_verified,
        "has_password": bool(getattr(user, "password_hash", None)),
        "display_name": user.display_name,
        "has_profile": user.profile is not None,
        "tier": tier,
        "is_admin_user": is_admin_user,
        "is_test_user": is_test_user,
        "can_manage_readings": bool(is_admin_user or is_test_user),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.put("/me")
async def update_me(
    req: UpdateDisplayNameRequest,
    user: User = Depends(get_current_public_user),
):
    user.display_name = req.display_name.strip() or None
    return {"detail": "Updated", "display_name": user.display_name}


@router.put("/me/password")
async def change_password(
    req: ChangePasswordRequest,
    user: User = Depends(get_current_public_user),
):
    if not user.password_hash:
        raise HTTPException(status_code=400, detail="No password set (OAuth account)")

    if not verify_password(req.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user.password_hash = hash_password(req.new_password)
    user.token_version = int(user.token_version or 0) + 1
    return {"detail": "Password changed successfully"}


@router.put("/me/email")
async def change_email(
    req: ChangeEmailRequest,
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    normalized_email = _normalize_email(req.new_email)
    if normalized_email == _normalize_email(user.email):
        raise HTTPException(status_code=400, detail="New email must be different")

    if user.password_hash:
        provided_password = (req.current_password or "").strip()
        if not provided_password:
            raise HTTPException(status_code=400, detail="Current password is required")
        if not verify_password(provided_password, user.password_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")

    existing = await db.execute(select(User.id).where(func.lower(User.email) == normalized_email))
    existing_id = existing.scalar()
    if existing_id and str(existing_id) != str(user.id):
        raise HTTPException(status_code=409, detail="Email already registered")

    user.email = normalized_email
    user.email_verified = False
    raw_token = await _generate_verification_token(user.id, db)
    delivered = await _send_verification_email(db, user, raw_token)
    return {
        "detail": (
            "Email updated. Verification link sent."
            if delivered
            else "Email updated, but verification email could not be sent. Use resend verification."
        ),
        "email": user.email,
        "email_verified": user.email_verified,
        "verification_sent": delivered,
    }


@router.get("/me/export")
async def export_account_data(
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    profile_payload = None
    if user.profile:
        profile_payload = {
            "birth_date": user.profile.birth_date.isoformat() if user.profile.birth_date else None,
            "birth_time": user.profile.birth_time.isoformat() if user.profile.birth_time else None,
            "birth_time_known": user.profile.birth_time_known,
            "birth_city": user.profile.birth_city,
            "birth_latitude": user.profile.birth_latitude,
            "birth_longitude": user.profile.birth_longitude,
            "birth_timezone": user.profile.birth_timezone,
            "house_system": user.profile.house_system,
        }

    subs_result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc())
    )
    subscriptions = [
        {
            "id": str(sub.id),
            "status": sub.status,
            "billing_interval": sub.billing_interval,
            "current_period_start": (
                sub.current_period_start.isoformat() if sub.current_period_start else None
            ),
            "current_period_end": (
                sub.current_period_end.isoformat() if sub.current_period_end else None
            ),
            "cancel_at_period_end": sub.cancel_at_period_end,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
        }
        for sub in subs_result.scalars().all()
    ]

    readings_result = await db.execute(
        select(PersonalReading)
        .where(PersonalReading.user_id == user.id)
        .order_by(PersonalReading.created_at.desc())
    )
    personal_readings = [
        {
            "id": str(reading.id),
            "tier": reading.tier,
            "date_context": reading.date_context.isoformat(),
            "content": reading.content,
            "created_at": reading.created_at.isoformat() if reading.created_at else None,
        }
        for reading in readings_result.scalars().all()
    ]

    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "user": {
            "id": str(user.id),
            "email": user.email,
            "email_verified": user.email_verified,
            "display_name": user.display_name,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        },
        "profile": profile_payload,
        "subscriptions": subscriptions,
        "personal_readings": personal_readings,
    }


@router.delete("/me")
async def delete_account(
    req: DeleteAccountRequest,
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    if user.password_hash:
        if not req.password:
            raise HTTPException(
                status_code=400,
                detail="Password is required to delete this account",
            )
        if not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

    db.add(
        AnalyticsEvent(
            event_type="user.account.delete",
            metadata_json={"user_id": str(user.id)},
        )
    )
    await db.delete(user)
    response = JSONResponse({"detail": "Account deleted"})
    _clear_user_auth_cookie(response)
    return response
