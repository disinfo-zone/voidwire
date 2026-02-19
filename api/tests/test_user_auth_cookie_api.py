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


def _scalar_first_result(value):
    result = MagicMock()
    result.scalars.return_value.first.return_value = value
    return result


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
        "apple": {"enabled": False, "client_id": ""},
        "any_enabled": True,
    }
    with patch(
        "api.routers.user_auth.load_public_oauth_providers",
        new=AsyncMock(return_value=payload),
    ):
        response = await client.get("/v1/user/auth/oauth/providers")
    assert response.status_code == 200
    assert response.json()["google"]["enabled"] is True


@pytest.mark.asyncio
async def test_oauth_google_rejects_when_provider_disabled(client: AsyncClient):
    with patch(
        "api.routers.user_auth.resolve_oauth_runtime_config",
        new=AsyncMock(return_value={"google": {"enabled": False}}),
    ):
        response = await client.post("/v1/user/auth/oauth/google", json={"id_token": "token"})
    assert response.status_code == 501
    assert "not configured" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_oauth_google_links_existing_user_by_verified_email(client: AsyncClient, mock_db):
    existing_user = SimpleNamespace(
        id=uuid.uuid4(),
        email="existing@test.local",
        google_id=None,
        email_verified=False,
        is_active=True,
        token_version=0,
    )
    mock_db.execute.side_effect = [
        _scalar_first_result(None),  # lookup by google_id
        _scalar_first_result(existing_user),  # lookup by email
    ]

    with (
        patch(
            "api.routers.user_auth.resolve_oauth_runtime_config",
            new=AsyncMock(
                return_value={"google": {"enabled": True, "client_id": "google-client"}}
            ),
        ),
        patch("google.auth.transport.requests.Request", return_value=object()),
        patch(
            "google.oauth2.id_token.verify_oauth2_token",
            return_value={
                "sub": "google_sub_123",
                "email": "existing@test.local",
                "email_verified": True,
                "name": "Existing User",
            },
        ),
    ):
        response = await client.post("/v1/user/auth/oauth/google", json={"id_token": "token"})

    assert response.status_code == 200
    assert existing_user.google_id == "google_sub_123"
    assert existing_user.email_verified is True
    assert "voidwire_user_token=" in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_oauth_google_rejects_unverified_email_linking(client: AsyncClient, mock_db):
    mock_db.execute.return_value = _scalar_first_result(None)

    with (
        patch(
            "api.routers.user_auth.resolve_oauth_runtime_config",
            new=AsyncMock(
                return_value={"google": {"enabled": True, "client_id": "google-client"}}
            ),
        ),
        patch("google.auth.transport.requests.Request", return_value=object()),
        patch(
            "google.oauth2.id_token.verify_oauth2_token",
            return_value={
                "sub": "google_sub_123",
                "email": "existing@test.local",
                "email_verified": False,
                "name": "Existing User",
            },
        ),
    ):
        response = await client.post("/v1/user/auth/oauth/google", json={"id_token": "token"})

    assert response.status_code == 401
    assert "must be verified" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_oauth_google_creates_new_verified_user(client: AsyncClient, mock_db):
    created_users = []

    def _capture_add(obj):
        if isinstance(obj, User):
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
            if getattr(obj, "is_active", None) is None:
                obj.is_active = True
            created_users.append(obj)

    mock_db.add = MagicMock(side_effect=_capture_add)
    mock_db.execute.side_effect = [
        _scalar_first_result(None),  # lookup by google_id
        _scalar_first_result(None),  # lookup by email
    ]

    with (
        patch(
            "api.routers.user_auth.resolve_oauth_runtime_config",
            new=AsyncMock(
                return_value={"google": {"enabled": True, "client_id": "google-client"}}
            ),
        ),
        patch("google.auth.transport.requests.Request", return_value=object()),
        patch(
            "google.oauth2.id_token.verify_oauth2_token",
            return_value={
                "sub": "google_sub_new",
                "email": "new-google@test.local",
                "email_verified": True,
                "name": "New Google User",
            },
        ),
    ):
        response = await client.post("/v1/user/auth/oauth/google", json={"id_token": "token"})

    assert response.status_code == 200
    assert len(created_users) == 1
    assert created_users[0].google_id == "google_sub_new"
    assert created_users[0].email_verified is True


@pytest.mark.asyncio
async def test_oauth_apple_rejects_when_provider_disabled(client: AsyncClient):
    with patch(
        "api.routers.user_auth.resolve_oauth_runtime_config",
        new=AsyncMock(return_value={"apple": {"enabled": False}}),
    ):
        response = await client.post(
            "/v1/user/auth/oauth/apple",
            json={"authorization_code": "auth_code"},
        )
    assert response.status_code == 501
    assert "not configured" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_oauth_apple_rejects_partial_configuration(client: AsyncClient):
    with patch(
        "api.routers.user_auth.resolve_oauth_runtime_config",
        new=AsyncMock(
            return_value={
                "apple": {
                    "enabled": True,
                    "client_id": "com.voidwire.web",
                    "team_id": "",
                    "key_id": "",
                    "private_key": "",
                }
            }
        ),
    ):
        response = await client.post(
            "/v1/user/auth/oauth/apple",
            json={"authorization_code": "auth_code"},
        )
    assert response.status_code == 501
    assert "partially configured" in response.json()["detail"].lower()
