"""Stripe billing configuration stored in site_settings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.models import SiteSetting
from voidwire.services.encryption import decrypt_value, encrypt_value

STRIPE_CONFIG_KEY = "billing.stripe"


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
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * max(4, len(value) - 8)}{value[-4:]}"


def _safe_decrypt(value: str) -> str:
    if not value:
        return ""
    try:
        return decrypt_value(value)
    except Exception:
        return ""


def _default_runtime_config() -> dict[str, Any]:
    settings = get_settings()
    secret_key = _normalize_text(settings.stripe_secret_key)
    publishable_key = _normalize_text(settings.stripe_publishable_key)
    webhook_secret = _normalize_text(settings.stripe_webhook_secret)
    is_configured = bool(secret_key and publishable_key)
    return {
        "enabled": is_configured,
        "secret_key": secret_key,
        "publishable_key": publishable_key,
        "webhook_secret": webhook_secret,
        "is_configured": is_configured,
        "webhook_is_configured": bool(webhook_secret),
    }


def _normalize_stored_config(payload: dict[str, Any] | None) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    return {
        "enabled": _coerce_bool(source.get("enabled"), False),
        "publishable_key": _normalize_text(source.get("publishable_key")),
        "secret_key_encrypted": _normalize_text(source.get("secret_key_encrypted")),
        "webhook_secret_encrypted": _normalize_text(source.get("webhook_secret_encrypted")),
    }


async def resolve_stripe_runtime_config(session: AsyncSession) -> dict[str, Any]:
    defaults = _default_runtime_config()
    row = await session.get(SiteSetting, STRIPE_CONFIG_KEY)
    stored = _normalize_stored_config(row.value if row else None)

    secret_key = _safe_decrypt(stored["secret_key_encrypted"]) or defaults["secret_key"]
    webhook_secret = (
        _safe_decrypt(stored["webhook_secret_encrypted"]) or defaults["webhook_secret"]
    )
    publishable_key = stored["publishable_key"] or defaults["publishable_key"]
    is_configured = bool(secret_key and publishable_key)
    enabled_raw = defaults["enabled"] if row is None else bool(stored["enabled"])

    return {
        "enabled": bool(enabled_raw and is_configured),
        "secret_key": secret_key,
        "publishable_key": publishable_key,
        "webhook_secret": webhook_secret,
        "is_configured": is_configured,
        "webhook_is_configured": bool(webhook_secret),
    }


def _admin_payload(
    runtime: dict[str, Any],
    *,
    updated_at: datetime | None,
    using_env_defaults: bool,
) -> dict[str, Any]:
    return {
        "enabled": bool(runtime.get("enabled")),
        "publishable_key": _normalize_text(runtime.get("publishable_key")),
        "secret_key_masked": _mask_secret(_normalize_text(runtime.get("secret_key"))),
        "webhook_secret_masked": _mask_secret(_normalize_text(runtime.get("webhook_secret"))),
        "is_configured": bool(runtime.get("is_configured")),
        "webhook_is_configured": bool(runtime.get("webhook_is_configured")),
        "using_env_defaults": using_env_defaults,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


async def load_stripe_config(session: AsyncSession) -> dict[str, Any]:
    row = await session.get(SiteSetting, STRIPE_CONFIG_KEY)
    runtime = await resolve_stripe_runtime_config(session)
    return _admin_payload(runtime, updated_at=row.updated_at if row else None, using_env_defaults=row is None)


async def save_stripe_config(session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    row = await session.get(SiteSetting, STRIPE_CONFIG_KEY)
    current = _normalize_stored_config(row.value if row else None)
    merged = dict(current)

    if "enabled" in payload:
        merged["enabled"] = _coerce_bool(payload.get("enabled"), False)
    if "publishable_key" in payload:
        merged["publishable_key"] = _normalize_text(payload.get("publishable_key"))
    if "secret_key" in payload:
        secret_key = _normalize_text(payload.get("secret_key"))
        merged["secret_key_encrypted"] = encrypt_value(secret_key) if secret_key else ""
    if "webhook_secret" in payload:
        webhook_secret = _normalize_text(payload.get("webhook_secret"))
        merged["webhook_secret_encrypted"] = (
            encrypt_value(webhook_secret) if webhook_secret else ""
        )

    now = datetime.now(UTC)
    if row is None:
        row = SiteSetting(
            key=STRIPE_CONFIG_KEY,
            value=merged,
            category="billing",
            description="Stripe billing credentials and toggle.",
            updated_at=now,
        )
        session.add(row)
    else:
        row.value = merged
        row.category = "billing"
        row.updated_at = now

    await session.flush()
    runtime = await resolve_stripe_runtime_config(session)
    return _admin_payload(runtime, updated_at=row.updated_at, using_env_defaults=False)
