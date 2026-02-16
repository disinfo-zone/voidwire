"""Site configuration helpers backed by site_settings."""

from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.models import SiteSetting

SITE_CONFIG_KEY = "site.config"
SITE_ASSET_KEY_PREFIX = "site.asset."
SITE_ASSET_ALLOWED_CONTENT_TYPES: dict[str, set[str]] = {
    "favicon": {
        "image/png",
        "image/svg+xml",
        "image/x-icon",
        "image/vnd.microsoft.icon",
        "image/jpeg",
        "image/webp",
    },
    "twittercard": {"image/png", "image/jpeg", "image/webp"},
}
SITE_ASSET_MAX_BYTES: dict[str, int] = {
    "favicon": 512 * 1024,
    "twittercard": 5 * 1024 * 1024,
}
_FILENAME_SANITIZER = re.compile(r"[^a-zA-Z0-9._-]+")


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


def _normalize_site_asset_kind(kind: str) -> str:
    normalized = _normalize_str(kind).lower()
    if normalized not in SITE_ASSET_ALLOWED_CONTENT_TYPES:
        raise ValueError("Unsupported site asset type")
    return normalized


def _default_asset_extension(content_type: str) -> str:
    if content_type in {"image/x-icon", "image/vnd.microsoft.icon"}:
        return ".ico"
    if content_type == "image/svg+xml":
        return ".svg"
    if content_type == "image/jpeg":
        return ".jpg"
    if content_type == "image/webp":
        return ".webp"
    return ".png"


def _sanitize_filename(filename: str, fallback: str) -> str:
    raw = _normalize_str(filename)
    sanitized = _FILENAME_SANITIZER.sub("-", raw).strip(".-").lower()
    if not sanitized:
        sanitized = fallback
    return sanitized[:120]


def site_asset_public_url(kind: str, version: int | None = None) -> str:
    normalized = _normalize_site_asset_kind(kind)
    base = f"/v1/site/assets/{normalized}"
    if version is None:
        return base
    return f"{base}?v={int(version)}"


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


async def save_site_asset(
    session: AsyncSession,
    *,
    kind: str,
    filename: str,
    content_type: str,
    content_bytes: bytes,
) -> dict[str, Any]:
    normalized_kind = _normalize_site_asset_kind(kind)
    normalized_content_type = _normalize_str(content_type).lower()
    allowed_types = SITE_ASSET_ALLOWED_CONTENT_TYPES[normalized_kind]
    if normalized_content_type not in allowed_types:
        raise ValueError("Unsupported image type for this asset")

    size_bytes = len(content_bytes or b"")
    if size_bytes <= 0:
        raise ValueError("Image upload is empty")

    max_bytes = SITE_ASSET_MAX_BYTES[normalized_kind]
    if size_bytes > max_bytes:
        raise ValueError(f"Image exceeds size limit ({max_bytes // 1024}KB)")

    ext = _default_asset_extension(normalized_content_type)
    sanitized_filename = _sanitize_filename(filename, f"{normalized_kind}{ext}")
    if "." not in sanitized_filename:
        sanitized_filename = f"{sanitized_filename}{ext}"

    now = datetime.now(UTC)
    payload = {
        "kind": normalized_kind,
        "filename": sanitized_filename,
        "content_type": normalized_content_type,
        "size_bytes": size_bytes,
        "uploaded_at": now.isoformat(),
        "data_base64": base64.b64encode(content_bytes).decode("ascii"),
    }

    key = f"{SITE_ASSET_KEY_PREFIX}{normalized_kind}"
    row = await session.get(SiteSetting, key)
    if row is None:
        row = SiteSetting(
            key=key,
            value=payload,
            category="site",
            description=f"Uploaded site asset ({normalized_kind})",
            updated_at=now,
        )
        session.add(row)
    else:
        row.value = payload
        row.category = "site"
        row.updated_at = now

    await session.flush()
    return {
        "kind": normalized_kind,
        "filename": sanitized_filename,
        "content_type": normalized_content_type,
        "size_bytes": size_bytes,
        "uploaded_at": now.isoformat(),
        "url": site_asset_public_url(normalized_kind, int(now.timestamp())),
    }


async def load_site_asset_content(
    session: AsyncSession,
    kind: str,
) -> tuple[bytes, str] | None:
    normalized_kind = _normalize_site_asset_kind(kind)
    row = await session.get(SiteSetting, f"{SITE_ASSET_KEY_PREFIX}{normalized_kind}")
    if row is None or not isinstance(row.value, dict):
        return None

    payload = row.value
    raw_b64 = payload.get("data_base64")
    if not isinstance(raw_b64, str) or not raw_b64.strip():
        return None

    try:
        raw_bytes = base64.b64decode(raw_b64, validate=True)
    except (ValueError, binascii.Error):
        return None

    max_bytes = SITE_ASSET_MAX_BYTES.get(normalized_kind, 5 * 1024 * 1024)
    if len(raw_bytes) > max_bytes:
        return None

    content_type = _normalize_str(payload.get("content_type")).lower() or "application/octet-stream"
    return raw_bytes, content_type


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
