"""Tests for admin SMTP configuration endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_smtp_config(client: AsyncClient):
    payload = {
        "enabled": True,
        "host": "smtp.example.com",
        "port": 587,
        "username": "mailer",
        "password_masked": "****1234",
        "from_email": "noreply@example.com",
        "from_name": "Voidwire",
        "reply_to": "",
        "use_ssl": False,
        "use_starttls": True,
        "is_configured": True,
    }
    with patch("api.routers.admin_site.load_smtp_config", new=AsyncMock(return_value=payload)):
        response = await client.get("/admin/site/email/smtp")
    assert response.status_code == 200
    assert response.json()["host"] == "smtp.example.com"


@pytest.mark.asyncio
async def test_update_smtp_config(client: AsyncClient):
    with patch(
        "api.routers.admin_site.save_smtp_config",
        new=AsyncMock(return_value={"enabled": True, "host": "smtp.example.com"}),
    ):
        response = await client.put(
            "/admin/site/email/smtp",
            json={
                "enabled": True,
                "host": "smtp.example.com",
                "port": 587,
                "username": "mailer",
                "password": "secret",
                "from_email": "noreply@example.com",
            },
        )
    assert response.status_code == 200
    assert response.json()["enabled"] is True


@pytest.mark.asyncio
async def test_send_smtp_test_email(client: AsyncClient):
    with patch(
        "api.routers.admin_site.send_transactional_email",
        new=AsyncMock(return_value=True),
    ):
        response = await client.post(
            "/admin/site/email/smtp/test",
            json={"to_email": "qa@example.com"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_get_oauth_config(client: AsyncClient):
    payload = {
        "google": {"enabled": True, "client_id": "google-client", "is_configured": True},
        "apple": {"enabled": False, "client_id": "", "is_configured": False},
        "any_enabled": True,
    }
    with patch("api.routers.admin_site.load_oauth_config", new=AsyncMock(return_value=payload)):
        response = await client.get("/admin/site/auth/oauth")
    assert response.status_code == 200
    assert response.json()["google"]["enabled"] is True


@pytest.mark.asyncio
async def test_update_oauth_config(client: AsyncClient):
    payload = {
        "google": {"enabled": True, "client_id": "google-client", "is_configured": True},
        "apple": {"enabled": False, "client_id": "", "is_configured": False},
        "any_enabled": True,
    }
    with patch("api.routers.admin_site.save_oauth_config", new=AsyncMock(return_value=payload)):
        response = await client.put(
            "/admin/site/auth/oauth",
            json={
                "google": {"enabled": True, "client_id": "google-client"},
                "apple": {"enabled": False},
            },
        )
    assert response.status_code == 200
    assert response.json()["google"]["client_id"] == "google-client"


@pytest.mark.asyncio
async def test_upload_site_asset_sets_favicon_url(client: AsyncClient):
    uploaded_asset = {
        "kind": "favicon",
        "filename": "favicon.png",
        "content_type": "image/png",
        "size_bytes": 5,
        "uploaded_at": "2026-02-16T00:00:00+00:00",
        "url": "/v1/site/assets/favicon?v=123",
    }
    with (
        patch("api.routers.admin_site.save_site_asset", new=AsyncMock(return_value=uploaded_asset)),
        patch(
            "api.routers.admin_site.load_site_config",
            new=AsyncMock(
                return_value={
                    "site_title": "VOIDWIRE",
                    "tagline": "",
                    "site_url": "https://voidwire.test",
                    "timezone": "UTC",
                    "favicon_url": "",
                    "meta_description": "",
                    "og_image_url": "",
                    "og_title_template": "{{title}} | {{site_title}}",
                    "twitter_handle": "",
                    "tracking_head": "",
                    "tracking_body": "",
                }
            ),
        ),
        patch(
            "api.routers.admin_site.save_site_config",
            new=AsyncMock(return_value={"favicon_url": "/v1/site/assets/favicon?v=123"}),
        ),
    ):
        response = await client.post(
            "/admin/site/assets",
            json={
                "kind": "favicon",
                "filename": "favicon.png",
                "content_type": "image/png",
                "data_base64": "aGVsbG8=",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "favicon"
    assert body["url"] == "/v1/site/assets/favicon?v=123"


@pytest.mark.asyncio
async def test_upload_site_asset_rejects_invalid_base64(client: AsyncClient):
    response = await client.post(
        "/admin/site/assets",
        json={
            "kind": "twittercard",
            "filename": "card.png",
            "content_type": "image/png",
            "data_base64": "not-valid-base64@@",
        },
    )
    assert response.status_code == 400
    assert "base64" in response.json()["detail"]
