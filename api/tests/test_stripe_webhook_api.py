"""Tests for Stripe webhook safety/idempotency behavior."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_webhook_duplicate_event_is_ignored(client: AsyncClient, mock_db):
    existing_result = MagicMock()
    existing_result.scalars.return_value.first.return_value = object()
    mock_db.execute.return_value = existing_result

    event = {
        "id": "evt_test_duplicate",
        "type": "invoice.paid",
        "data": {"object": {"subscription": "sub_test_123"}},
    }
    with patch("api.routers.stripe_webhook.verify_webhook_signature", return_value=event):
        response = await client.post(
            "/v1/stripe/webhook",
            content=b"{}",
            headers={"stripe-signature": "sig_test"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "duplicate_ignored"


@pytest.mark.asyncio
async def test_webhook_rejects_missing_event_id(client: AsyncClient):
    event = {
        "type": "invoice.paid",
        "data": {"object": {"subscription": "sub_test_123"}},
    }
    with patch("api.routers.stripe_webhook.verify_webhook_signature", return_value=event):
        response = await client.post(
            "/v1/stripe/webhook",
            content=b"{}",
            headers={"stripe-signature": "sig_test"},
        )

    assert response.status_code == 400
    assert "Invalid webhook payload" in response.json()["detail"]
