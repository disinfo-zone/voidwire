"""Content page storage helpers backed by site_settings."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voidwire.models import SiteSetting

CONTENT_SETTING_PREFIX = "content.page."

DEFAULT_CONTENT_PAGES: dict[str, dict[str, Any]] = {
    "about": {
        "slug": "about",
        "title": "About",
        "sections": [
            {
                "heading": "Transmission",
                "body": (
                    "VOIDWIRE is a daily dispatch from the celestial wire -- an automated reading of planetary "
                    "positions, lunar phases, and astronomical transits, rendered into prose by machine "
                    "intelligence and delivered each day at the threshold between night and morning.\n\n"
                    "Each reading is generated from precise ephemeris calculations, interpreting the geometry "
                    "of the solar system as it appears from Earth. The positions are real. The aspects are exact. "
                    "The language is synthetic."
                ),
            },
            {
                "heading": "Philosophy",
                "body": (
                    "This project sits at the intersection of ancient pattern-recognition and modern computation. "
                    "The sky has been read for millennia. VOIDWIRE simply automates the observation, stripping away "
                    "human bias while preserving the structure of the interpretive tradition.\n\n"
                    "No claims are made about causality or influence. The transmissions are literary artifacts shaped "
                    "by astronomical data -- nothing more, nothing less."
                ),
            },
            {
                "heading": "Typography & Design",
                "body": (
                    "The site is set in EB Garamond, a revival of Claude Garamont's sixteenth-century type. The "
                    "choice is deliberate: a typeface designed for sustained reading, rooted in the same era that "
                    "produced the first printed ephemerides and astronomical tables.\n\n"
                    "The void-black background eliminates distraction. Text is rendered in muted parchment tones -- "
                    "warm enough to read comfortably, dim enough to feel like reading by candlelight. The design "
                    "prioritizes the word above all else."
                ),
            },
            {
                "heading": "Colophon",
                "body": (
                    "Built with Astro and Svelte. Ephemeris calculations via Swiss Ephemeris. Served from the "
                    "void.\n\nThe source is the sky. The medium is the wire. The rest is noise."
                ),
            },
        ],
    },
    "privacy": {
        "slug": "privacy",
        "title": "Privacy Policy",
        "sections": [
            {
                "heading": "Data We Collect",
                "body": (
                    "Voidwire stores account identity data (email, auth credentials), profile inputs for natal "
                    "chart computation, subscription status, and generated readings tied to your account."
                ),
            },
            {
                "heading": "How Data Is Used",
                "body": (
                    "Collected data is used to authenticate access, generate personalized readings, process billing, "
                    "operate analytics, and maintain service reliability. Data is not sold."
                ),
            },
            {
                "heading": "Data Controls",
                "body": (
                    "Users can request data export, revoke active sessions, and delete accounts through authenticated "
                    "account endpoints. Retention cleanup periodically removes expired auth tokens and aged telemetry."
                ),
            },
        ],
    },
    "terms": {
        "slug": "terms",
        "title": "Terms of Service",
        "sections": [
            {
                "heading": "Service Scope",
                "body": (
                    "Voidwire provides software-generated astrological content for informational and entertainment "
                    "purposes. No professional, legal, medical, or financial advice is provided."
                ),
            },
            {
                "heading": "Account Responsibility",
                "body": (
                    "You are responsible for safeguarding your account credentials and all activity under your "
                    "account. Abuse, unauthorized access attempts, or service disruption may result in suspension."
                ),
            },
            {
                "heading": "Billing Terms",
                "body": (
                    "Paid features are billed through Stripe. Subscription status, renewal dates, and cancellation "
                    "state are governed by your active Stripe subscription and customer portal actions."
                ),
            },
        ],
    },
    "billing-policy": {
        "slug": "billing-policy",
        "title": "Billing Policy",
        "sections": [
            {
                "heading": "Subscriptions",
                "body": (
                    "Pro access is subscription-based unless manually overridden by administration for support/testing. "
                    "Promotions and discount code validity are subject to configured expiration and redemption limits."
                ),
            },
            {
                "heading": "Failed Payments",
                "body": (
                    "Failed or past-due payments may downgrade account access until billing is restored. Billing "
                    "events are reconciled against Stripe records to keep local entitlement state accurate."
                ),
            },
            {
                "heading": "Refund Handling",
                "body": (
                    "Refund and charge dispute handling follows your Stripe transaction record and applicable law. "
                    "Contact support with the account email and transaction timestamp for assistance."
                ),
            },
        ],
    },
    "disclaimer": {
        "slug": "disclaimer",
        "title": "Disclaimer",
        "sections": [
            {
                "heading": "No Professional Advice",
                "body": (
                    "Voidwire outputs are generated text informed by astronomical inputs. They are not a substitute "
                    "for professional legal, medical, mental health, or financial guidance."
                ),
            },
            {
                "heading": "Availability",
                "body": (
                    "Service availability, generated outputs, and feature access may change without notice as the "
                    "platform evolves and safety controls are improved."
                ),
            },
        ],
    },
}


def _setting_key(slug: str) -> str:
    return f"{CONTENT_SETTING_PREFIX}{slug}"


def known_content_slugs() -> list[str]:
    return sorted(DEFAULT_CONTENT_PAGES.keys())


def is_known_content_slug(slug: str) -> bool:
    return slug in DEFAULT_CONTENT_PAGES


def _sanitize_sections(raw_sections: Any) -> list[dict[str, str]]:
    if not isinstance(raw_sections, list):
        return []
    cleaned: list[dict[str, str]] = []
    for item in raw_sections:
        if not isinstance(item, dict):
            continue
        heading = str(item.get("heading", "")).strip()
        body = str(item.get("body", "")).strip()
        if not heading and not body:
            continue
        cleaned.append({"heading": heading, "body": body})
    return cleaned


def normalize_content_payload(slug: str, payload: Any) -> dict[str, Any]:
    base = deepcopy(DEFAULT_CONTENT_PAGES.get(slug, {"slug": slug, "title": slug.title(), "sections": []}))
    if isinstance(payload, dict):
        title = str(payload.get("title", "")).strip()
        if title:
            base["title"] = title
        sections = _sanitize_sections(payload.get("sections"))
        if sections:
            base["sections"] = sections
    base["slug"] = slug
    if not base.get("sections"):
        base["sections"] = []
    return base


async def get_content_page(session: AsyncSession, slug: str) -> dict[str, Any]:
    if not is_known_content_slug(slug):
        raise KeyError(f"Unknown content slug: {slug}")

    setting = await session.get(SiteSetting, _setting_key(slug))
    payload = setting.value if setting is not None else None
    page = normalize_content_payload(slug, payload)
    page["updated_at"] = (
        setting.updated_at.isoformat()
        if setting is not None and getattr(setting, "updated_at", None) is not None
        else None
    )
    return page


async def list_content_pages(session: AsyncSession) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for slug in known_content_slugs():
        page = await get_content_page(session, slug)
        pages.append(
            {
                "slug": slug,
                "title": page.get("title", slug.title()),
                "sections_count": len(page.get("sections", [])),
                "updated_at": page.get("updated_at"),
            }
        )
    return pages


async def save_content_page(session: AsyncSession, slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not is_known_content_slug(slug):
        raise KeyError(f"Unknown content slug: {slug}")

    normalized = normalize_content_payload(slug, payload)
    now = datetime.now(timezone.utc)
    setting = await session.get(SiteSetting, _setting_key(slug))
    if setting is None:
        setting = SiteSetting(
            key=_setting_key(slug),
            value={"title": normalized["title"], "sections": normalized["sections"]},
            category="content",
            description=f"Content payload for /{slug}",
            updated_at=now,
        )
        session.add(setting)
    else:
        setting.value = {"title": normalized["title"], "sections": normalized["sections"]}
        setting.category = "content"
        setting.updated_at = now

    await session.flush()

    normalized["updated_at"] = (
        setting.updated_at.isoformat()
        if getattr(setting, "updated_at", None) is not None
        else None
    )
    return normalized
