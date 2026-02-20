"""Tests for admin SMTP configuration endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_smtp_config(client: AsyncClient):
    payload = {
        "enabled": True,
        "provider": "smtp",
        "host": "smtp.example.com",
        "port": 587,
        "username": "mailer",
        "password_masked": "****1234",
        "resend_api_key_masked": "",
        "resend_api_base_url": "https://api.resend.com",
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
                "provider": "smtp",
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
async def test_get_email_templates(client: AsyncClient):
    payload = {
        "verification": {
            "subject": "Verify account",
            "text_body": "Verify at {{verify_link}}",
            "html_body": "<p>Verify</p>",
        },
        "password_reset": {
            "subject": "Reset password",
            "text_body": "Reset at {{reset_link}}",
            "html_body": "<p>Reset</p>",
        },
        "test_email": {
            "subject": "Test",
            "text_body": "Test body",
            "html_body": "<p>Test</p>",
        },
    }
    with patch("api.routers.admin_site.load_email_templates", new=AsyncMock(return_value=payload)):
        response = await client.get("/admin/site/email/templates")
    assert response.status_code == 200
    assert response.json()["verification"]["subject"] == "Verify account"


@pytest.mark.asyncio
async def test_update_email_templates(client: AsyncClient):
    payload = {
        "verification": {
            "subject": "Verify account",
            "text_body": "Verify at {{verify_link}}",
            "html_body": "<p>Verify</p>",
        },
        "password_reset": {
            "subject": "Reset password",
            "text_body": "Reset at {{reset_link}}",
            "html_body": "<p>Reset</p>",
        },
        "test_email": {
            "subject": "Test",
            "text_body": "Test body",
            "html_body": "<p>Test</p>",
        },
    }
    with patch("api.routers.admin_site.save_email_templates", new=AsyncMock(return_value=payload)):
        response = await client.put(
            "/admin/site/email/templates",
            json={
                "verification": {
                    "subject": "Verify account",
                    "text_body": "Verify at {{verify_link}}",
                    "html_body": "<p>Verify</p>",
                }
            },
        )
    assert response.status_code == 200
    assert response.json()["verification"]["subject"] == "Verify account"


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
async def test_send_smtp_test_email_returns_provider_error(client: AsyncClient):
    with patch(
        "api.routers.admin_site.send_transactional_email",
        new=AsyncMock(side_effect=RuntimeError("Resend API request failed (400): Invalid from address")),
    ):
        response = await client.post(
            "/admin/site/email/smtp/test",
            json={"to_email": "qa@example.com"},
        )
    assert response.status_code == 400
    assert "Invalid from address" in response.json()["detail"]


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
async def test_get_stripe_config(client: AsyncClient):
    payload = {
        "enabled": True,
        "publishable_key": "pk_test_123",
        "secret_key_masked": "sk_t****1234",
        "webhook_secret_masked": "whse****1234",
        "is_configured": True,
        "webhook_is_configured": True,
    }
    with patch("api.routers.admin_site.load_stripe_config", new=AsyncMock(return_value=payload)):
        response = await client.get("/admin/site/billing/stripe")
    assert response.status_code == 200
    assert response.json()["enabled"] is True


@pytest.mark.asyncio
async def test_update_stripe_config(client: AsyncClient):
    payload = {
        "enabled": True,
        "publishable_key": "pk_test_123",
        "secret_key_masked": "sk_t****1234",
        "webhook_secret_masked": "whse****1234",
        "is_configured": True,
        "webhook_is_configured": True,
    }
    with patch("api.routers.admin_site.save_stripe_config", new=AsyncMock(return_value=payload)):
        response = await client.put(
            "/admin/site/billing/stripe",
            json={
                "enabled": True,
                "publishable_key": "pk_test_123",
                "secret_key": "sk_test_123",
                "webhook_secret": "whsec_123",
            },
        )
    assert response.status_code == 200
    assert response.json()["publishable_key"] == "pk_test_123"


@pytest.mark.asyncio
async def test_run_stripe_connectivity_check(client: AsyncClient):
    check_payload = {
        "status": "ok",
        "message": "Stripe connectivity check passed",
        "enabled": True,
        "account_id": "acct_123",
        "api_mode": "test",
        "secret_key_mode": "test",
        "publishable_key_mode": "test",
        "key_mode_match": True,
        "webhook_ready": True,
        "active_price_count": 2,
        "sample_prices": [],
        "warnings": [],
    }
    with (
        patch(
            "api.routers.admin_site.resolve_stripe_runtime_config",
            new=AsyncMock(
                return_value={
                    "secret_key": "sk_test_123",
                    "publishable_key": "pk_test_123",
                    "webhook_secret": "whsec_123",
                }
            ),
        ),
        patch(
            "api.routers.admin_site.run_stripe_connectivity_check",
            return_value=check_payload,
        ),
    ):
        response = await client.post("/admin/site/billing/stripe/test")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["account_id"] == "acct_123"


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
