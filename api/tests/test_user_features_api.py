"""Tests for user account/profile/subscription endpoints."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from api.dependencies import get_current_public_user, get_db
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def public_user():
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="user@test.local",
        is_active=True,
        profile=None,
        subscriptions=[],
    )


@pytest.fixture
async def user_client(app, mock_db, public_user):
    async def _override_db():
        yield mock_db

    async def _override_user():
        return public_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_public_user] = _override_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _stripe_settings() -> SimpleNamespace:
    return SimpleNamespace(
        stripe_secret_key="sk_test_123",
        stripe_publishable_key="pk_test_123",
        site_url="https://voidwire.test",
        admin_url="https://admin.voidwire.test",
    )


@pytest.mark.asyncio
async def test_birth_data_rejects_invalid_time_when_known(user_client: AsyncClient):
    response = await user_client.put(
        "/v1/user/profile/birth-data",
        json={
            "birth_date": "1990-05-05",
            "birth_time": "99:77",
            "birth_time_known": True,
            "birth_city": "New York, NY",
            "birth_latitude": 40.7128,
            "birth_longitude": -74.0060,
            "birth_timezone": "America/New_York",
            "house_system": "placidus",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_birth_data_rejects_future_birth_date(user_client: AsyncClient):
    future_date = (date.today() + timedelta(days=1)).isoformat()
    response = await user_client.put(
        "/v1/user/profile/birth-data",
        json={
            "birth_date": future_date,
            "birth_time": None,
            "birth_time_known": False,
            "birth_city": "London",
            "birth_latitude": 51.5072,
            "birth_longitude": -0.1276,
            "birth_timezone": "Europe/London",
            "house_system": "placidus",
        },
    )
    assert response.status_code == 400
    assert "future" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_birth_data_rejects_invalid_timezone(user_client: AsyncClient):
    response = await user_client.put(
        "/v1/user/profile/birth-data",
        json={
            "birth_date": "1990-05-05",
            "birth_time": "10:30",
            "birth_time_known": True,
            "birth_city": "Los Angeles, CA",
            "birth_latitude": 34.0522,
            "birth_longitude": -118.2437,
            "birth_timezone": "Not/A_Real_Timezone",
            "house_system": "placidus",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_checkout_rejects_untrusted_success_url(user_client: AsyncClient):
    with patch("api.routers.user_subscription.get_settings", return_value=_stripe_settings()):
        response = await user_client.post(
            "/v1/user/subscription/checkout",
            json={
                "price_id": "price_test_123",
                "success_url": "https://evil.example/success",
                "cancel_url": "https://voidwire.test/dashboard",
            },
        )
    assert response.status_code == 400
    assert "success_url" in response.json()["detail"]


@pytest.mark.asyncio
async def test_portal_rejects_untrusted_return_url(user_client: AsyncClient):
    with patch("api.routers.user_subscription.get_settings", return_value=_stripe_settings()):
        response = await user_client.post(
            "/v1/user/subscription/portal",
            json={"return_url": "https://evil.example/portal"},
        )
    assert response.status_code == 400
    assert "return_url" in response.json()["detail"]


@pytest.mark.asyncio
async def test_checkout_rejects_unknown_price(user_client: AsyncClient):
    with (
        patch("api.routers.user_subscription.get_settings", return_value=_stripe_settings()),
        patch("api.routers.user_subscription.is_price_active_recurring", return_value=False),
    ):
        response = await user_client.post(
            "/v1/user/subscription/checkout",
            json={
                "price_id": "price_unknown",
                "success_url": "https://voidwire.test/dashboard?ok=1",
                "cancel_url": "https://voidwire.test/dashboard",
            },
        )
    assert response.status_code == 400
    assert "price_id" in response.json()["detail"]


@pytest.mark.asyncio
async def test_checkout_allows_whitelisted_redirect_urls(user_client: AsyncClient):
    with (
        patch("api.routers.user_subscription.get_settings", return_value=_stripe_settings()),
        patch("api.routers.user_subscription.is_price_active_recurring", return_value=True),
        patch(
            "api.routers.user_subscription.get_or_create_customer",
            new=AsyncMock(return_value="cus_test"),
        ),
        patch(
            "api.routers.user_subscription.create_checkout_session",
            return_value="https://checkout.stripe.com/pay/cs_test",
        ),
    ):
        response = await user_client.post(
            "/v1/user/subscription/checkout",
            json={
                "price_id": "price_known",
                "success_url": "https://voidwire.test/dashboard?ok=1",
                "cancel_url": "https://voidwire.test/dashboard",
            },
        )
    assert response.status_code == 200
    assert response.json()["checkout_url"].startswith("https://checkout.stripe.com/")


@pytest.mark.asyncio
async def test_checkout_applies_valid_discount_code(user_client: AsyncClient):
    discount = SimpleNamespace(stripe_promotion_code_id="promo_123")
    with (
        patch("api.routers.user_subscription.get_settings", return_value=_stripe_settings()),
        patch("api.routers.user_subscription.is_price_active_recurring", return_value=True),
        patch(
            "api.routers.user_subscription.resolve_usable_discount_code",
            new=AsyncMock(return_value=discount),
        ),
        patch(
            "api.routers.user_subscription.get_or_create_customer",
            new=AsyncMock(return_value="cus_test"),
        ),
        patch(
            "api.routers.user_subscription.create_checkout_session",
            return_value="https://checkout.stripe.com/pay/cs_test_with_discount",
        ) as create_checkout_mock,
    ):
        response = await user_client.post(
            "/v1/user/subscription/checkout",
            json={
                "price_id": "price_known",
                "success_url": "https://voidwire.test/dashboard?ok=1",
                "cancel_url": "https://voidwire.test/dashboard",
                "discount_code": "test50",
            },
        )
    assert response.status_code == 200
    assert response.json()["checkout_url"].endswith("cs_test_with_discount")
    create_checkout_mock.assert_called_once()
    assert create_checkout_mock.call_args.kwargs["promotion_code_id"] == "promo_123"


@pytest.mark.asyncio
async def test_checkout_rejects_invalid_discount_code(user_client: AsyncClient):
    with (
        patch("api.routers.user_subscription.get_settings", return_value=_stripe_settings()),
        patch("api.routers.user_subscription.is_price_active_recurring", return_value=True),
        patch(
            "api.routers.user_subscription.resolve_usable_discount_code",
            new=AsyncMock(return_value=None),
        ),
    ):
        response = await user_client.post(
            "/v1/user/subscription/checkout",
            json={
                "price_id": "price_known",
                "success_url": "https://voidwire.test/dashboard?ok=1",
                "cancel_url": "https://voidwire.test/dashboard",
                "discount_code": "bogus",
            },
        )
    assert response.status_code == 400
    assert "discount code" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_checkout_returns_actionable_discount_error(user_client: AsyncClient):
    with (
        patch("api.routers.user_subscription.get_settings", return_value=_stripe_settings()),
        patch("api.routers.user_subscription.is_price_active_recurring", return_value=True),
        patch(
            "api.routers.user_subscription.get_or_create_customer",
            new=AsyncMock(return_value="cus_test"),
        ),
        patch(
            "api.routers.user_subscription.create_checkout_session",
            side_effect=Exception("No such promotion code: promo_123"),
        ),
    ):
        response = await user_client.post(
            "/v1/user/subscription/checkout",
            json={
                "price_id": "price_known",
                "success_url": "https://voidwire.test/dashboard?ok=1",
                "cancel_url": "https://voidwire.test/dashboard",
            },
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "Discount code is invalid"
