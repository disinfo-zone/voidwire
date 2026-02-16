"""Tests for cookie-based user auth session behavior."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from api.middleware.auth import create_access_token
from httpx import AsyncClient
from voidwire.models import User


@pytest.mark.asyncio
async def test_register_sets_http_only_auth_cookie(client: AsyncClient, mock_db):
    def side_effect_add(obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

    mock_db.add = MagicMock(side_effect=side_effect_add)

    response = await client.post(
        "/v1/user/auth/register",
        json={
            "email": "newuser@test.local",
            "password": "super-secret-password",
            "display_name": "Test User",
        },
    )

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "voidwire_user_token=" in set_cookie
    assert "voidwire_csrf_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie


@pytest.mark.asyncio
async def test_logout_clears_auth_cookie(client: AsyncClient):
    response = await client.post("/v1/user/auth/logout")

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "voidwire_user_token=" in set_cookie
    assert "Max-Age=0" in set_cookie


@pytest.mark.asyncio
async def test_me_accepts_user_jwt_from_cookie(client: AsyncClient, mock_db):
    user_id = uuid.uuid4()
    mock_user = SimpleNamespace(
        id=user_id,
        email="cookie-user@test.local",
        email_verified=True,
        display_name="Cookie User",
        profile=None,
        is_active=True,
        created_at=datetime(2026, 2, 15, tzinfo=UTC),
    )
    mock_db.get.return_value = mock_user
    admin_lookup_result = MagicMock()
    admin_lookup_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = admin_lookup_result

    token = create_access_token(user_id=str(user_id), token_type="user")
    response = await client.get(
        "/v1/user/auth/me",
        headers={"Cookie": f"voidwire_user_token={token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(user_id)
    assert response.json()["can_manage_readings"] is False

    # Ensure dependency fetched from the public User model lookup path.
    assert mock_db.get.await_args.args[0] is User


@pytest.mark.asyncio
async def test_oauth_provider_status_endpoint(client: AsyncClient):
    payload = {
        "google": {"enabled": True, "client_id": "google-client"},
        "apple": {"enabled": False},
        "any_enabled": True,
    }
    with patch(
        "api.routers.user_auth.load_public_oauth_providers",
        new=AsyncMock(return_value=payload),
    ):
        response = await client.get("/v1/user/auth/oauth/providers")
    assert response.status_code == 200
    assert response.json()["google"]["enabled"] is True
