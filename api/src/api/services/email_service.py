"""SMTP configuration + transactional email sending."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import SiteSetting
from voidwire.services.encryption import decrypt_value, encrypt_value

logger = logging.getLogger(__name__)

SMTP_CONFIG_KEY = "email.smtp"


def default_smtp_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "host": "",
        "port": 587,
        "username": "",
        "password_encrypted": "",
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
    base["host"] = _normalize_text(source.get("host"))
    base["port"] = _coerce_port(source.get("port"))
    base["username"] = _normalize_text(source.get("username"))
    base["password_encrypted"] = _normalize_text(source.get("password_encrypted"))
    base["from_email"] = _normalize_text(source.get("from_email")).lower()
    base["from_name"] = _normalize_text(source.get("from_name")) or "Voidwire"
    base["reply_to"] = _normalize_text(source.get("reply_to")).lower()
    base["use_ssl"] = _coerce_bool(source.get("use_ssl"), False)
    base["use_starttls"] = _coerce_bool(source.get("use_starttls"), True)
    if base["use_ssl"]:
        base["use_starttls"] = False
    return base


def smtp_is_configured(config: dict[str, Any]) -> bool:
    if not _normalize_text(config.get("host")):
        return False
    if not _normalize_text(config.get("from_email")):
        return False
    return _coerce_port(config.get("port")) > 0


def _response_payload(config: dict[str, Any]) -> dict[str, Any]:
    password_plain = ""
    encrypted = _normalize_text(config.get("password_encrypted"))
    if encrypted:
        try:
            password_plain = decrypt_value(encrypted)
        except Exception:
            password_plain = ""
    return {
        "enabled": _coerce_bool(config.get("enabled"), False),
        "host": _normalize_text(config.get("host")),
        "port": _coerce_port(config.get("port")),
        "username": _normalize_text(config.get("username")),
        "password_masked": _mask_secret(password_plain),
        "from_email": _normalize_text(config.get("from_email")).lower(),
        "from_name": _normalize_text(config.get("from_name")) or "Voidwire",
        "reply_to": _normalize_text(config.get("reply_to")).lower(),
        "use_ssl": _coerce_bool(config.get("use_ssl"), False),
        "use_starttls": _coerce_bool(config.get("use_starttls"), True),
        "is_configured": smtp_is_configured(config),
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
        return {
            **config,
            "password": password,
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
        "host",
        "port",
        "username",
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

    normalized = normalize_smtp_config(merged)
    now = datetime.now(UTC)
    if current_row is None:
        current_row = SiteSetting(
            key=SMTP_CONFIG_KEY,
            value=normalized,
            category="email",
            description="SMTP configuration for transactional emails.",
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


async def send_transactional_email(
    session: AsyncSession,
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> bool:
    config = await load_smtp_config(session, include_secret_password=True)
    enabled = _coerce_bool(config.get("enabled"), False)
    if not enabled:
        logger.info("SMTP is disabled; skipping transactional email send")
        return False
    if not smtp_is_configured(config):
        logger.warning(
            "SMTP is enabled but not fully configured; skipping transactional email send"
        )
        return False

    try:
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
    except Exception:
        logger.exception("Failed sending transactional email to %s", to_email)
        return False
