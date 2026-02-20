"""Tests for transactional email service provider selection."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from api.services.email_service import send_transactional_email


@pytest.mark.asyncio
async def test_send_transactional_email_skips_when_disabled():
    with patch(
        "api.services.email_service.load_smtp_config",
        new=AsyncMock(return_value={"enabled": False}),
    ):
        delivered = await send_transactional_email(
            AsyncMock(),
            to_email="qa@example.com",
            subject="Subject",
            text_body="Body",
        )
    assert delivered is False


@pytest.mark.asyncio
async def test_send_transactional_email_uses_resend_provider():
    with (
        patch(
            "api.services.email_service.load_smtp_config",
            new=AsyncMock(
                return_value={
                    "enabled": True,
                    "provider": "resend",
                    "from_email": "noreply@example.com",
                    "from_name": "Voidwire",
                    "reply_to": "",
                    "resend_api_key": "re_test_123",
                    "resend_api_base_url": "https://api.resend.com",
                }
            ),
        ),
        patch(
            "api.services.email_service._send_resend_email_async",
            new=AsyncMock(return_value=None),
        ) as resend_mock,
    ):
        delivered = await send_transactional_email(
            AsyncMock(),
            to_email="qa@example.com",
            subject="Subject",
            text_body="Body",
        )
    assert delivered is True
    resend_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_transactional_email_uses_smtp_provider():
    with (
        patch(
            "api.services.email_service.load_smtp_config",
            new=AsyncMock(
                return_value={
                    "enabled": True,
                    "provider": "smtp",
                    "host": "smtp.example.com",
                    "port": 587,
                    "username": "mailer",
                    "password": "secret",
                    "from_email": "noreply@example.com",
                    "from_name": "Voidwire",
                    "reply_to": "",
                    "use_ssl": False,
                    "use_starttls": True,
                }
            ),
        ),
        patch(
            "api.services.email_service.asyncio.to_thread",
            new=AsyncMock(return_value=None),
        ) as to_thread_mock,
    ):
        delivered = await send_transactional_email(
            AsyncMock(),
            to_email="qa@example.com",
            subject="Subject",
            text_body="Body",
        )
    assert delivered is True
    to_thread_mock.assert_awaited_once()
