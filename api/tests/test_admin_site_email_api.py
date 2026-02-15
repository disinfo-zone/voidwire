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

