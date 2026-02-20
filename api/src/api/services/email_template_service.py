"""Email template configuration and placeholder rendering."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import SiteSetting

EMAIL_TEMPLATE_CONFIG_KEY = "email.templates"
EMAIL_TEMPLATE_KEYS = ("verification", "password_reset", "test_email")
EMAIL_TEMPLATE_FIELDS = ("subject", "text_body", "html_body")


def default_email_templates() -> dict[str, dict[str, str]]:
    return {
        "verification": {
            "subject": "Verify your Voidwire account",
            "text_body": (
                "Welcome to {{site_name}}.\n\n"
                "Verify your email by opening this link:\n{{verify_link}}\n\n"
                "If the link does not work, submit this token via the verify-email API endpoint:\n"
                "{{token}}\n"
            ),
            "html_body": (
                "<p>Welcome to {{site_name}}.</p>"
                '<p>Verify your email: <a href="{{verify_link}}">{{verify_link}}</a></p>'
                "<p>If the link does not work, use this token in the verify-email API endpoint:</p>"
                "<pre>{{token}}</pre>"
            ),
        },
        "password_reset": {
            "subject": "Reset your Voidwire password",
            "text_body": (
                "We received a request to reset your {{site_name}} password.\n\n"
                "Reset link:\n{{reset_link}}\n\n"
                "If you did not request this, you can ignore this email."
            ),
            "html_body": (
                "<p>We received a request to reset your {{site_name}} password.</p>"
                '<p><a href="{{reset_link}}">Reset your password</a></p>'
                "<p>If you did not request this, you can ignore this email.</p>"
            ),
        },
        "test_email": {
            "subject": "Voidwire Email Delivery Test",
            "text_body": (
                "This is a test email from {{site_name}}.\n\n"
                "If you received this message, your email delivery settings are working."
            ),
            "html_body": (
                "<p>This is a test email from <strong>{{site_name}}</strong>.</p>"
                "<p>If you received this message, your email delivery settings are working.</p>"
            ),
        },
    }


def _normalize_text(value: Any, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def normalize_email_templates(payload: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    source = payload if isinstance(payload, dict) else {}
    defaults = default_email_templates()
    normalized: dict[str, dict[str, str]] = {}
    for key in EMAIL_TEMPLATE_KEYS:
        source_template = source.get(key) if isinstance(source.get(key), dict) else {}
        default_template = defaults[key]
        normalized[key] = {
            "subject": _normalize_text(
                source_template.get("subject"),
                default=default_template["subject"],
            ),
            "text_body": _normalize_text(
                source_template.get("text_body"),
                default=default_template["text_body"],
            ),
            "html_body": _normalize_text(
                source_template.get("html_body"),
                default=default_template["html_body"],
            ),
        }
    return normalized


async def load_email_templates(session: AsyncSession) -> dict[str, Any]:
    row = await session.get(SiteSetting, EMAIL_TEMPLATE_CONFIG_KEY)
    templates = normalize_email_templates(row.value if row and isinstance(row.value, dict) else None)
    return {
        **templates,
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
    }


async def save_email_templates(session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    current_row = await session.get(SiteSetting, EMAIL_TEMPLATE_CONFIG_KEY)
    current_raw = (
        current_row.value
        if current_row is not None and isinstance(current_row.value, dict)
        else default_email_templates()
    )
    current = normalize_email_templates(current_raw)
    merged = {**current}

    for key in EMAIL_TEMPLATE_KEYS:
        template_payload = payload.get(key) if isinstance(payload.get(key), dict) else None
        if template_payload is None:
            continue
        next_template = dict(merged.get(key, {}))
        for field in EMAIL_TEMPLATE_FIELDS:
            if field in template_payload:
                value = _normalize_text(template_payload.get(field))
                if value:
                    next_template[field] = value
        merged[key] = next_template

    normalized = normalize_email_templates(merged)
    now = datetime.now(UTC)
    if current_row is None:
        current_row = SiteSetting(
            key=EMAIL_TEMPLATE_CONFIG_KEY,
            value=normalized,
            category="email",
            description="Transactional email templates.",
            updated_at=now,
        )
        session.add(current_row)
    else:
        current_row.value = normalized
        current_row.category = "email"
        current_row.updated_at = now
    await session.flush()
    return {
        **normalized,
        "updated_at": current_row.updated_at.isoformat() if current_row.updated_at else None,
    }


_PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


def _render_template(template: str, context: dict[str, Any]) -> str:
    if not template:
        return ""

    def _replace(match: re.Match[str]) -> str:
        key = str(match.group(1) or "").strip()
        value = context.get(key, "")
        return str(value if value is not None else "")

    return _PLACEHOLDER_PATTERN.sub(_replace, template)


async def load_rendered_email_template(
    session: AsyncSession,
    *,
    template_key: str,
    context: dict[str, Any] | None = None,
) -> tuple[str, str, str]:
    normalized_key = str(template_key or "").strip().lower()
    if normalized_key not in EMAIL_TEMPLATE_KEYS:
        raise ValueError(f"Unknown email template: {template_key}")
    payload = await load_email_templates(session)
    template = payload.get(normalized_key) if isinstance(payload.get(normalized_key), dict) else {}
    local_context = dict(context or {})
    subject = _render_template(_normalize_text(template.get("subject")), local_context)
    text_body = _render_template(_normalize_text(template.get("text_body")), local_context)
    html_body = _render_template(_normalize_text(template.get("html_body")), local_context)
    return subject, text_body, html_body
