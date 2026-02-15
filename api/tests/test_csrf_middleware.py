"""Tests for CSRF middleware on cookie-authenticated mutation requests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_user_logout_with_auth_cookie_requires_csrf_header(
    unauthenticated_client: AsyncClient,
):
    response = await unauthenticated_client.post(
        "/v1/user/auth/logout",
        headers={"Cookie": "voidwire_user_token=fake.jwt.token; voidwire_csrf_token=abc123"},
    )
    assert response.status_code == 403
    assert "csrf" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_user_logout_accepts_matching_csrf_cookie_and_header(
    unauthenticated_client: AsyncClient,
):
    response = await unauthenticated_client.post(
        "/v1/user/auth/logout",
        headers={
            "Cookie": "voidwire_user_token=fake.jwt.token; voidwire_csrf_token=abc123",
            "X-CSRF-Token": "abc123",
            "Origin": "https://voidwire.disinfo.zone",
        },
    )
    assert response.status_code == 200
    assert response.json()["detail"] == "Logged out"


@pytest.mark.asyncio
async def test_user_logout_rejects_cross_site_origin(unauthenticated_client: AsyncClient):
    response = await unauthenticated_client.post(
        "/v1/user/auth/logout",
        headers={
            "Cookie": "voidwire_user_token=fake.jwt.token; voidwire_csrf_token=abc123",
            "X-CSRF-Token": "abc123",
            "Origin": "https://evil.example",
        },
    )
    assert response.status_code == 403
    assert "origin" in response.json()["detail"].lower()
