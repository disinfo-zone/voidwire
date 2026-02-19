"""OAuth provider configuration stored in site_settings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.models import SiteSetting
from voidwire.services.encryption import decrypt_value, encrypt_value

OAUTH_CONFIG_KEY = "auth.oauth"


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * max(4, len(value) - 4)}{value[-4:]}"


def _safe_decrypt(value: str) -> str:
    if not value:
        return ""
    try:
        return decrypt_value(value)
    except Exception:
        return ""


def _provider_is_configured(payload: dict[str, Any], provider: str) -> bool:
    if provider == "google":
        return bool(_normalize_text(payload.get("client_id")))
    if provider == "apple":
        return bool(
            _normalize_text(payload.get("client_id"))
            and _normalize_text(payload.get("team_id"))
            and _normalize_text(payload.get("key_id"))
            and _normalize_text(payload.get("private_key"))
        )
    return False


def _default_runtime_config() -> dict[str, dict[str, Any]]:
    settings = get_settings()
    return {
        "google": {
            "enabled": bool(_normalize_text(settings.google_client_id)),
            "client_id": _normalize_text(settings.google_client_id),
            "client_secret": _normalize_text(settings.google_client_secret),
        },
        "apple": {
            "enabled": bool(
                _normalize_text(settings.apple_client_id)
                and _normalize_text(settings.apple_team_id)
                and _normalize_text(settings.apple_key_id)
                and _normalize_text(settings.apple_private_key)
            ),
            "client_id": _normalize_text(settings.apple_client_id),
            "team_id": _normalize_text(settings.apple_team_id),
            "key_id": _normalize_text(settings.apple_key_id),
            "private_key": _normalize_text(settings.apple_private_key),
        },
    }


def _normalize_stored_config(payload: dict[str, Any] | None) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    google = source.get("google") if isinstance(source.get("google"), dict) else {}
    apple = source.get("apple") if isinstance(source.get("apple"), dict) else {}

    return {
        "google": {
            "enabled": _coerce_bool(google.get("enabled"), False),
            "client_id": _normalize_text(google.get("client_id")),
            "client_secret_encrypted": _normalize_text(google.get("client_secret_encrypted")),
        },
        "apple": {
            "enabled": _coerce_bool(apple.get("enabled"), False),
            "client_id": _normalize_text(apple.get("client_id")),
            "team_id": _normalize_text(apple.get("team_id")),
            "key_id": _normalize_text(apple.get("key_id")),
            "private_key_encrypted": _normalize_text(apple.get("private_key_encrypted")),
        },
    }


async def resolve_oauth_runtime_config(session: AsyncSession) -> dict[str, dict[str, Any]]:
    defaults = _default_runtime_config()
    row = await session.get(SiteSetting, OAUTH_CONFIG_KEY)
    stored = _normalize_stored_config(row.value if row else None)

    google_secret = _safe_decrypt(stored["google"]["client_secret_encrypted"])
    apple_private_key = _safe_decrypt(stored["apple"]["private_key_encrypted"])

    google_client_id = stored["google"]["client_id"] or defaults["google"]["client_id"]
    apple_client_id = stored["apple"]["client_id"] or defaults["apple"]["client_id"]
    apple_team_id = stored["apple"]["team_id"] or defaults["apple"]["team_id"]
    apple_key_id = stored["apple"]["key_id"] or defaults["apple"]["key_id"]

    runtime = {
        "google": {
            "enabled": defaults["google"]["enabled"] if row is None else bool(stored["google"]["enabled"]),
            "client_id": google_client_id,
            "client_secret": google_secret or defaults["google"]["client_secret"],
        },
        "apple": {
            "enabled": defaults["apple"]["enabled"] if row is None else bool(stored["apple"]["enabled"]),
            "client_id": apple_client_id,
            "team_id": apple_team_id,
            "key_id": apple_key_id,
            "private_key": apple_private_key or defaults["apple"]["private_key"],
        },
    }

    runtime["google"]["is_configured"] = _provider_is_configured(runtime["google"], "google")
    runtime["apple"]["is_configured"] = _provider_is_configured(runtime["apple"], "apple")
    runtime["google"]["enabled"] = bool(
        runtime["google"]["enabled"] and runtime["google"]["is_configured"]
    )
    runtime["apple"]["enabled"] = bool(runtime["apple"]["enabled"] and runtime["apple"]["is_configured"])
    return runtime


def _admin_payload(runtime: dict[str, dict[str, Any]], updated_at: datetime | None) -> dict[str, Any]:
    google_secret = _normalize_text(runtime["google"].get("client_secret"))
    apple_private_key = _normalize_text(runtime["apple"].get("private_key"))
    return {
        "google": {
            "enabled": bool(runtime["google"].get("enabled")),
            "client_id": _normalize_text(runtime["google"].get("client_id")),
            "client_secret_masked": _mask_secret(google_secret),
            "is_configured": bool(runtime["google"].get("is_configured")),
        },
        "apple": {
            "enabled": bool(runtime["apple"].get("enabled")),
            "client_id": _normalize_text(runtime["apple"].get("client_id")),
            "team_id": _normalize_text(runtime["apple"].get("team_id")),
            "key_id": _normalize_text(runtime["apple"].get("key_id")),
            "private_key_masked": _mask_secret(apple_private_key),
            "is_configured": bool(runtime["apple"].get("is_configured")),
        },
        "any_enabled": bool(runtime["google"].get("enabled") or runtime["apple"].get("enabled")),
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


async def load_oauth_config(session: AsyncSession) -> dict[str, Any]:
    row = await session.get(SiteSetting, OAUTH_CONFIG_KEY)
    runtime = await resolve_oauth_runtime_config(session)
    updated_at = row.updated_at if row else None
    return _admin_payload(runtime, updated_at)


async def save_oauth_config(session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    row = await session.get(SiteSetting, OAUTH_CONFIG_KEY)
    current = _normalize_stored_config(row.value if row else None)

    next_google = dict(current["google"])
    next_apple = dict(current["apple"])
    google_payload = payload.get("google") if isinstance(payload.get("google"), dict) else {}
    apple_payload = payload.get("apple") if isinstance(payload.get("apple"), dict) else {}

    if "enabled" in google_payload:
        next_google["enabled"] = _coerce_bool(google_payload.get("enabled"), False)
    if "client_id" in google_payload:
        next_google["client_id"] = _normalize_text(google_payload.get("client_id"))
    if "client_secret" in google_payload:
        secret = _normalize_text(google_payload.get("client_secret"))
        next_google["client_secret_encrypted"] = encrypt_value(secret) if secret else ""

    if "enabled" in apple_payload:
        next_apple["enabled"] = _coerce_bool(apple_payload.get("enabled"), False)
    if "client_id" in apple_payload:
        next_apple["client_id"] = _normalize_text(apple_payload.get("client_id"))
    if "team_id" in apple_payload:
        next_apple["team_id"] = _normalize_text(apple_payload.get("team_id"))
    if "key_id" in apple_payload:
        next_apple["key_id"] = _normalize_text(apple_payload.get("key_id"))
    if "private_key" in apple_payload:
        private_key = _normalize_text(apple_payload.get("private_key"))
        next_apple["private_key_encrypted"] = encrypt_value(private_key) if private_key else ""

    stored = {
        "google": next_google,
        "apple": next_apple,
    }
    now = datetime.now(UTC)
    if row is None:
        row = SiteSetting(
            key=OAUTH_CONFIG_KEY,
            value=stored,
            category="auth",
            description="OAuth provider configuration for user sign-in.",
            updated_at=now,
        )
        session.add(row)
    else:
        row.value = stored
        row.category = "auth"
        row.updated_at = now
    await session.flush()

    runtime = await resolve_oauth_runtime_config(session)
    return _admin_payload(runtime, row.updated_at)


async def load_public_oauth_providers(session: AsyncSession) -> dict[str, Any]:
    runtime = await resolve_oauth_runtime_config(session)
    return {
        "google": {
            "enabled": bool(runtime["google"]["enabled"]),
            "client_id": _normalize_text(runtime["google"].get("client_id")),
        },
        "apple": {
            "enabled": bool(runtime["apple"]["enabled"]),
            "client_id": _normalize_text(runtime["apple"].get("client_id")),
        },
        "any_enabled": bool(runtime["google"]["enabled"] or runtime["apple"]["enabled"]),
    }
