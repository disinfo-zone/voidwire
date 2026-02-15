"""Site configuration helpers backed by site_settings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.models import SiteSetting

SITE_CONFIG_KEY = "site.config"


def default_site_config() -> dict[str, Any]:
    settings = get_settings()
    return {
        "site_title": "VOIDWIRE",
        "tagline": "Daily transmissions from the celestial wire.",
        "site_url": settings.site_url,
        "timezone": settings.timezone,
        "favicon_url": "",
        "meta_description": "Daily transmissions from the celestial wire.",
        "og_image_url": "",
        "og_title_template": "{{title}} | {{site_title}}",
        "twitter_handle": "",
        "tracking_head": "",
        "tracking_body": "",
    }


def _normalize_str(value: Any) -> str:
    return str(value or "").strip()


def normalize_site_config(payload: dict[str, Any] | None) -> dict[str, Any]:
    base = default_site_config()
    source = payload if isinstance(payload, dict) else {}
    for key in base.keys():
        if key in source:
            base[key] = _normalize_str(source.get(key))
    if not base["site_title"]:
        base["site_title"] = "VOIDWIRE"
    if not base["meta_description"]:
        base["meta_description"] = "Daily transmissions from the celestial wire."
    if not base["og_title_template"]:
        base["og_title_template"] = "{{title}} | {{site_title}}"
    if not base["site_url"]:
        base["site_url"] = get_settings().site_url
    if not base["timezone"]:
        base["timezone"] = get_settings().timezone
    return base


async def load_site_config(session: AsyncSession) -> dict[str, Any]:
    row = await session.get(SiteSetting, SITE_CONFIG_KEY)
    cfg = normalize_site_config(row.value if row else None)
    cfg["updated_at"] = row.updated_at.isoformat() if row and row.updated_at else None
    return cfg


async def save_site_config(session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_site_config(payload)
    row = await session.get(SiteSetting, SITE_CONFIG_KEY)
    now = datetime.now(UTC)
    if row is None:
        row = SiteSetting(
            key=SITE_CONFIG_KEY,
            value=normalized,
            category="site",
            description="Public site configuration (metadata, tracking, branding).",
            updated_at=now,
        )
        session.add(row)
    else:
        row.value = normalized
        row.category = "site"
        row.updated_at = now
    await session.flush()
    normalized["updated_at"] = row.updated_at.isoformat() if row.updated_at else None
    return normalized
