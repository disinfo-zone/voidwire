"""Transactional email configuration + sending (SMTP or Resend API)."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import SiteSetting
from voidwire.services.encryption import decrypt_value, encrypt_value

logger = logging.getLogger(__name__)

SMTP_CONFIG_KEY = "email.smtp"


def default_smtp_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "provider": "smtp",
        "host": "",
        "port": 587,
        "username": "",
        "password_encrypted": "",
        "resend_api_key_encrypted": "",
        "resend_api_base_url": "https://api.resend.com",
        "from_email": "",
        "from_name": "Voidwire",
        "reply_to": "",
        "use_ssl": False,
        "use_starttls": True,
    }


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


def _coerce_port(value: Any) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return 587
    if port < 1 or port > 65535:
        return 587
    return port


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_provider(value: Any) -> str:
    provider = _normalize_text(value).lower()
    if provider in {"smtp", "resend"}:
        return provider
    return "smtp"


def _normalize_base_url(value: Any, *, default: str) -> str:
    raw = _normalize_text(value)
    if not raw:
        return default
    return raw.rstrip("/")


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * max(4, len(value) - 4)}{value[-4:]}"


def normalize_smtp_config(payload: dict[str, Any] | None) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    base = default_smtp_config()
    base["enabled"] = _coerce_bool(source.get("enabled"), False)
    base["provider"] = _normalize_provider(source.get("provider"))
    base["host"] = _normalize_text(source.get("host"))
    base["port"] = _coerce_port(source.get("port"))
    base["username"] = _normalize_text(source.get("username"))
    base["password_encrypted"] = _normalize_text(source.get("password_encrypted"))
    base["resend_api_key_encrypted"] = _normalize_text(source.get("resend_api_key_encrypted"))
    base["resend_api_base_url"] = _normalize_base_url(
        source.get("resend_api_base_url"),
        default="https://api.resend.com",
    )
    base["from_email"] = _normalize_text(source.get("from_email")).lower()
    base["from_name"] = _normalize_text(source.get("from_name")) or "Voidwire"
    base["reply_to"] = _normalize_text(source.get("reply_to")).lower()
    base["use_ssl"] = _coerce_bool(source.get("use_ssl"), False)
    base["use_starttls"] = _coerce_bool(source.get("use_starttls"), True)
    if base["use_ssl"]:
        base["use_starttls"] = False
    return base


def smtp_is_configured(config: dict[str, Any]) -> bool:
    if _normalize_provider(config.get("provider")) != "smtp":
        return False
    if not _normalize_text(config.get("host")):
        return False
    if not _normalize_text(config.get("from_email")):
        return False
    return _coerce_port(config.get("port")) > 0


def resend_is_configured(config: dict[str, Any]) -> bool:
    if _normalize_provider(config.get("provider")) != "resend":
        return False
    if not _normalize_text(config.get("from_email")):
        return False
    return bool(_normalize_text(config.get("resend_api_key")))


def email_delivery_is_configured(config: dict[str, Any]) -> bool:
    provider = _normalize_provider(config.get("provider"))
    if provider == "resend":
        return resend_is_configured(config)
    return smtp_is_configured(config)


def _provider_configuration_error(config: dict[str, Any], provider: str) -> str | None:
    normalized = _normalize_provider(provider)
    if normalized == "resend":
        if not _normalize_text(config.get("from_email")):
            return "Resend email delivery requires from_email."
        if not _normalize_text(config.get("resend_api_key")):
            return "Resend email delivery requires resend_api_key."
        return None

    if not _normalize_text(config.get("host")):
        return "SMTP email delivery requires host."
    if not _normalize_text(config.get("from_email")):
        return "SMTP email delivery requires from_email."
    if _coerce_port(config.get("port")) <= 0:
        return "SMTP email delivery requires a valid port."
    return None


def _response_payload(config: dict[str, Any]) -> dict[str, Any]:
    password_plain = ""
    resend_api_key_plain = ""
    encrypted = _normalize_text(config.get("password_encrypted"))
    if encrypted:
        try:
            password_plain = decrypt_value(encrypted)
        except Exception:
            password_plain = ""
    resend_encrypted = _normalize_text(config.get("resend_api_key_encrypted"))
    if resend_encrypted:
        try:
            resend_api_key_plain = decrypt_value(resend_encrypted)
        except Exception:
            resend_api_key_plain = ""
    return {
        "enabled": _coerce_bool(config.get("enabled"), False),
        "provider": _normalize_provider(config.get("provider")),
        "host": _normalize_text(config.get("host")),
        "port": _coerce_port(config.get("port")),
        "username": _normalize_text(config.get("username")),
        "password_masked": _mask_secret(password_plain),
        "resend_api_key_masked": _mask_secret(resend_api_key_plain),
        "resend_api_base_url": _normalize_base_url(
            config.get("resend_api_base_url"),
            default="https://api.resend.com",
        ),
        "from_email": _normalize_text(config.get("from_email")).lower(),
        "from_name": _normalize_text(config.get("from_name")) or "Voidwire",
        "reply_to": _normalize_text(config.get("reply_to")).lower(),
        "use_ssl": _coerce_bool(config.get("use_ssl"), False),
        "use_starttls": _coerce_bool(config.get("use_starttls"), True),
        "is_configured": email_delivery_is_configured(config),
    }


async def load_smtp_config(
    session: AsyncSession,
    *,
    include_secret_password: bool = False,
) -> dict[str, Any]:
    row = await session.get(SiteSetting, SMTP_CONFIG_KEY)
    config = normalize_smtp_config(row.value if row and isinstance(row.value, dict) else None)
    if include_secret_password:
        encrypted = _normalize_text(config.get("password_encrypted"))
        password = ""
        if encrypted:
            try:
                password = decrypt_value(encrypted)
            except Exception:
                password = ""
        resend_encrypted = _normalize_text(config.get("resend_api_key_encrypted"))
        resend_api_key = ""
        if resend_encrypted:
            try:
                resend_api_key = decrypt_value(resend_encrypted)
            except Exception:
                resend_api_key = ""
        return {
            **config,
            "password": password,
            "resend_api_key": resend_api_key,
        }
    payload = _response_payload(config)
    payload["updated_at"] = row.updated_at.isoformat() if row and row.updated_at else None
    return payload


async def save_smtp_config(
    session: AsyncSession,
    payload: dict[str, Any],
) -> dict[str, Any]:
    current_row = await session.get(SiteSetting, SMTP_CONFIG_KEY)
    current_raw = (
        current_row.value
        if current_row is not None and isinstance(current_row.value, dict)
        else default_smtp_config()
    )
    current = normalize_smtp_config(current_raw)

    merged = dict(current)
    for key in (
        "enabled",
        "provider",
        "host",
        "port",
        "username",
        "resend_api_base_url",
        "from_email",
        "from_name",
        "reply_to",
        "use_ssl",
        "use_starttls",
    ):
        if key in payload:
            merged[key] = payload[key]

    if "password" in payload:
        raw_password = _normalize_text(payload.get("password"))
        if raw_password:
            merged["password_encrypted"] = encrypt_value(raw_password)
        else:
            merged["password_encrypted"] = ""

    if "resend_api_key" in payload:
        raw_key = _normalize_text(payload.get("resend_api_key"))
        if raw_key:
            merged["resend_api_key_encrypted"] = encrypt_value(raw_key)
        else:
            merged["resend_api_key_encrypted"] = ""

    normalized = normalize_smtp_config(merged)
    now = datetime.now(UTC)
    if current_row is None:
        current_row = SiteSetting(
            key=SMTP_CONFIG_KEY,
            value=normalized,
            category="email",
            description="Transactional email configuration (SMTP or Resend).",
            updated_at=now,
        )
        session.add(current_row)
    else:
        current_row.value = normalized
        current_row.category = "email"
        current_row.updated_at = now
    await session.flush()
    response = _response_payload(normalized)
    response["updated_at"] = current_row.updated_at.isoformat() if current_row.updated_at else None
    return response


def _build_sender(from_email: str, from_name: str) -> str:
    if not from_name:
        return from_email
    return f"{from_name} <{from_email}>"


def _send_email_sync(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    from_email: str,
    from_name: str,
    reply_to: str,
    use_ssl: bool,
    use_starttls: bool,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> None:
    message = EmailMessage()
    message["From"] = _build_sender(from_email, from_name)
    message["To"] = to_email
    message["Subject"] = subject
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    if use_ssl:
        smtp_client: smtplib.SMTP = smtplib.SMTP_SSL(host=host, port=port, timeout=15)
    else:
        smtp_client = smtplib.SMTP(host=host, port=port, timeout=15)

    with smtp_client as smtp:
        smtp.ehlo()
        if use_starttls and not use_ssl:
            smtp.starttls()
            smtp.ehlo()
        if username:
            smtp.login(username, password)
        smtp.send_message(message)


async def _send_resend_email_async(
    *,
    api_key: str,
    api_base_url: str,
    from_email: str,
    from_name: str,
    reply_to: str,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> None:
    base_url = _normalize_base_url(api_base_url, default="https://api.resend.com")
    payload: dict[str, Any] = {
        "from": _build_sender(from_email, from_name),
        "to": [_normalize_text(to_email).lower()],
        "subject": _normalize_text(subject),
        "text": text_body,
    }
    if html_body:
        payload["html"] = html_body
    if reply_to:
        payload["reply_to"] = _normalize_text(reply_to).lower()

    headers = {
        "Authorization": f"Bearer {_normalize_text(api_key)}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(f"{base_url}/emails", json=payload, headers=headers)
    if response.status_code >= 400:
        message = ""
        try:
            data = response.json()
            message = str(data.get("message") or data.get("error") or "").strip()
        except Exception:
            message = ""
        detail = f": {message}" if message else ""
        raise RuntimeError(f"Resend API request failed ({response.status_code}){detail}")


async def send_transactional_email(
    session: AsyncSession,
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    raise_on_error: bool = False,
) -> bool:
    config = await load_smtp_config(session, include_secret_password=True)
    enabled = _coerce_bool(config.get("enabled"), False)
    provider = _normalize_provider(config.get("provider"))
    if not enabled:
        message = "Email delivery is disabled."
        logger.info("Email delivery is disabled; skipping transactional email send")
        if raise_on_error:
            raise RuntimeError(message)
        return False
    configuration_error = _provider_configuration_error(config, provider)
    if configuration_error:
        logger.warning(
            "Email delivery is enabled but provider '%s' is not fully configured: %s",
            provider,
            configuration_error,
        )
        if raise_on_error:
            raise RuntimeError(configuration_error)
        return False

    try:
        if provider == "resend":
            await _send_resend_email_async(
                api_key=_normalize_text(config.get("resend_api_key")),
                api_base_url=_normalize_base_url(
                    config.get("resend_api_base_url"),
                    default="https://api.resend.com",
                ),
                from_email=_normalize_text(config.get("from_email")).lower(),
                from_name=_normalize_text(config.get("from_name")) or "Voidwire",
                reply_to=_normalize_text(config.get("reply_to")).lower(),
                to_email=_normalize_text(to_email).lower(),
                subject=_normalize_text(subject),
                text_body=text_body,
                html_body=html_body,
            )
        else:
            await asyncio.to_thread(
                _send_email_sync,
                host=_normalize_text(config.get("host")),
                port=_coerce_port(config.get("port")),
                username=_normalize_text(config.get("username")),
                password=_normalize_text(config.get("password")),
                from_email=_normalize_text(config.get("from_email")).lower(),
                from_name=_normalize_text(config.get("from_name")) or "Voidwire",
                reply_to=_normalize_text(config.get("reply_to")).lower(),
                use_ssl=_coerce_bool(config.get("use_ssl"), False),
                use_starttls=_coerce_bool(config.get("use_starttls"), True),
                to_email=_normalize_text(to_email).lower(),
                subject=_normalize_text(subject),
                text_body=text_body,
                html_body=html_body,
            )
        return True
    except Exception as exc:
        logger.exception(
            "Failed sending transactional email via provider '%s' to %s",
            provider,
            to_email,
        )
        if raise_on_error:
            message = str(exc).strip() or "Email delivery failed."
            raise RuntimeError(message) from exc
        return False
