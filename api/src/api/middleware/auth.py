"""JWT + TOTP authentication."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import bcrypt
import pyotp
from jose import jwt
from voidwire.config import get_settings


def _coerce_token_version(value: object) -> int:
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


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_access_token(
    user_id: str,
    expires_delta: timedelta | None = None,
    token_type: str = "admin",
    token_version: int = 0,
) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": token_type,
        "tv": _coerce_token_version(token_version),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

def generate_totp_secret() -> str:
    return pyotp.random_base32()

def get_totp_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="Voidwire")

def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code)
