"""Tests for cookie-based user auth session behavior."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from api.middleware.auth import create_access_token
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
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


@pytest.mark.asyncio
async def test_change_email_requires_current_password_for_password_users(client: AsyncClient, mock_db):
    user_id = uuid.uuid4()
    user = SimpleNamespace(
        id=user_id,
        email="existing@test.local",
        email_verified=True,
        password_hash="hashed-password",
        is_active=True,
        token_version=0,
    )
    mock_db.get.return_value = user
    duplicate_lookup = MagicMock()
    duplicate_lookup.scalar.return_value = None
    mock_db.execute.return_value = duplicate_lookup
    token = create_access_token(user_id=str(user_id), token_type="user", token_version=0)
    csrf = "csrf-test-token"

    response = await client.put(
        "/v1/user/auth/me/email",
        headers={
            "Cookie": f"voidwire_user_token={token}; voidwire_csrf_token={csrf}",
            "x-csrf-token": csrf,
        },
        json={"new_email": "new-email@test.local"},
    )

    assert response.status_code == 400
    assert "current password is required" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_change_email_updates_user_and_sends_verification(client: AsyncClient, mock_db):
    user_id = uuid.uuid4()
    user = SimpleNamespace(
        id=user_id,
        email="old@test.local",
        email_verified=True,
        password_hash="hashed-password",
        is_active=True,
        token_version=0,
    )
    mock_db.get.return_value = user
    duplicate_lookup = MagicMock()
    duplicate_lookup.scalar.return_value = None
    mock_db.execute.return_value = duplicate_lookup
    token = create_access_token(user_id=str(user_id), token_type="user", token_version=0)
    csrf = "csrf-test-token"

    with (
        patch("api.routers.user_auth.verify_password", return_value=True),
        patch(
            "api.routers.user_auth._generate_verification_token",
            new=AsyncMock(return_value="token-123"),
        ) as token_mock,
        patch(
            "api.routers.user_auth._send_verification_email",
            new=AsyncMock(return_value=True),
        ) as send_mock,
    ):
        response = await client.put(
            "/v1/user/auth/me/email",
            headers={
                "Cookie": f"voidwire_user_token={token}; voidwire_csrf_token={csrf}",
                "x-csrf-token": csrf,
            },
            json={"new_email": "new-email@test.local", "current_password": "correct-password"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "new-email@test.local"
    assert body["email_verified"] is False
    assert body["verification_sent"] is True
    assert user.email == "new-email@test.local"
    assert user.email_verified is False
    token_mock.assert_awaited_once()
    send_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_email_is_idempotent_for_already_used_token(client: AsyncClient, mock_db):
    raw_token = "a" * 64
    token_record = SimpleNamespace(
        user_id=uuid.uuid4(),
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        used_at=datetime.now(UTC),
        expires_at=datetime(2027, 1, 1, tzinfo=UTC),
    )
    user = SimpleNamespace(
        id=token_record.user_id,
        email="verified@test.local",
        is_active=True,
        email_verified=True,
    )
    mock_db.execute.return_value = _scalar_first_result(token_record)
    mock_db.get.return_value = user

    response = await client.post(
        "/v1/user/auth/verify-email",
        json={"token": raw_token},
    )

    assert response.status_code == 200
    assert response.json()["detail"] == "Email already verified"
    assert user.email_verified is True


@pytest.mark.asyncio
async def test_verify_email_accepts_wrapped_token_input(client: AsyncClient, mock_db):
    raw_token = "b" * 64
    token_record = SimpleNamespace(
        user_id=uuid.uuid4(),
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        used_at=None,
        expires_at=datetime(2027, 1, 1, tzinfo=UTC),
    )
    user = SimpleNamespace(
        id=token_record.user_id,
        email="unverified@test.local",
        is_active=True,
        email_verified=False,
    )
    mock_db.execute.return_value = _scalar_first_result(token_record)
    mock_db.get.return_value = user

    response = await client.post(
        "/v1/user/auth/verify-email",
        json={"token": f"<{raw_token}>"},
    )

    assert response.status_code == 200
    assert response.json()["detail"] == "Email verified successfully"
    assert user.email_verified is True
    assert token_record.used_at is not None


@pytest.mark.asyncio
async def test_delete_account_allows_empty_body_for_passwordless_user(client: AsyncClient, mock_db):
    user_id = uuid.uuid4()
    user = SimpleNamespace(
        id=user_id,
        email="oauth-only@test.local",
        email_verified=True,
        password_hash=None,
        is_active=True,
        token_version=0,
    )
    mock_db.get.return_value = user
    token = create_access_token(user_id=str(user_id), token_type="user", token_version=0)
    csrf = "csrf-test-token"

    response = await client.delete(
        "/v1/user/auth/me",
        headers={
            "Cookie": f"voidwire_user_token={token}; voidwire_csrf_token={csrf}",
            "x-csrf-token": csrf,
        },
    )

    assert response.status_code == 200
    assert response.json()["detail"] == "Account deleted"
    assert response.json()["mode"] == "hard"
    mock_db.delete.assert_awaited_once_with(user)
    mock_db.flush.assert_awaited()
    mock_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_delete_account_requires_password_for_password_user(client: AsyncClient, mock_db):
    user_id = uuid.uuid4()
    user = SimpleNamespace(
        id=user_id,
        email="password-user@test.local",
        email_verified=True,
        password_hash="hashed-password",
        is_active=True,
        token_version=0,
    )
    mock_db.get.return_value = user
    token = create_access_token(user_id=str(user_id), token_type="user", token_version=0)
    csrf = "csrf-test-token"

    response = await client.delete(
        "/v1/user/auth/me",
        headers={
            "Cookie": f"voidwire_user_token={token}; voidwire_csrf_token={csrf}",
            "x-csrf-token": csrf,
        },
    )

    assert response.status_code == 400
    assert "password is required" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_account_falls_back_to_soft_delete_on_integrity_error(
    client: AsyncClient,
    mock_db,
):
    user_id = uuid.uuid4()
    user = SimpleNamespace(
        id=user_id,
        email="soft-delete@test.local",
        email_verified=True,
        password_hash=None,
        google_id="google-123",
        apple_id="apple-123",
        display_name="Soft Delete User",
        pro_override=True,
        pro_override_reason="manual",
        pro_override_until=datetime(2026, 12, 31, tzinfo=UTC),
        token_version=1,
        is_active=True,
    )
    mock_db.get.side_effect = [user, user]
    mock_db.flush.side_effect = [
        IntegrityError("DELETE FROM users", {}, Exception("fk violation")),
        None,
        None,
    ]
    token = create_access_token(user_id=str(user_id), token_type="user", token_version=1)
    csrf = "csrf-test-token"

    response = await client.delete(
        "/v1/user/auth/me",
        headers={
            "Cookie": f"voidwire_user_token={token}; voidwire_csrf_token={csrf}",
            "x-csrf-token": csrf,
        },
    )

    assert response.status_code == 200
    assert response.json()["detail"] == "Account deleted"
    assert response.json()["mode"] == "soft"
    assert user.is_active is False
    assert user.email.startswith("deleted+")
    assert user.google_id is None
    assert user.apple_id is None
    assert user.display_name is None
    assert user.pro_override is False
    assert user.pro_override_reason is None
    assert user.pro_override_until is None
    mock_db.delete.assert_awaited_once_with(user)
    mock_db.rollback.assert_awaited_once()
    assert mock_db.execute.await_count >= 6
    mock_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_delete_account_handles_deferred_constraint_failure_on_commit(
    client: AsyncClient,
    mock_db,
):
    user_id = uuid.uuid4()
    user = SimpleNamespace(
        id=user_id,
        email="deferred-soft-delete@test.local",
        email_verified=True,
        password_hash=None,
        google_id="google-123",
        apple_id="apple-123",
        display_name="Deferred Soft Delete User",
        pro_override=True,
        pro_override_reason="manual",
        pro_override_until=datetime(2026, 12, 31, tzinfo=UTC),
        token_version=1,
        is_active=True,
    )
    mock_db.get.side_effect = [user, user]
    mock_db.commit.side_effect = [
        IntegrityError("COMMIT", {}, Exception("deferred fk violation")),
        None,
    ]
    token = create_access_token(user_id=str(user_id), token_type="user", token_version=1)
    csrf = "csrf-test-token"

    response = await client.delete(
        "/v1/user/auth/me",
        headers={
            "Cookie": f"voidwire_user_token={token}; voidwire_csrf_token={csrf}",
            "x-csrf-token": csrf,
        },
    )

    assert response.status_code == 200
    assert response.json()["detail"] == "Account deleted"
    assert response.json()["mode"] == "soft"
    assert user.is_active is False
    assert user.email.startswith("deleted+")
    assert user.google_id is None
    assert user.apple_id is None
    assert user.display_name is None
    assert user.pro_override is False
    assert user.pro_override_reason is None
    assert user.pro_override_until is None
    mock_db.rollback.assert_awaited_once()
    assert mock_db.execute.await_count >= 6
    assert mock_db.commit.await_count == 2


@pytest.mark.asyncio
async def test_resend_verification_by_email_sends_for_unverified_user(client: AsyncClient, mock_db):
    user = SimpleNamespace(
        id=uuid.uuid4(),
        email="user@test.local",
        email_verified=False,
        is_active=True,
    )
    mock_db.execute.return_value = _scalar_first_result(user)

    with (
        patch(
            "api.routers.user_auth._generate_verification_token",
            new=AsyncMock(return_value="token-123"),
        ) as token_mock,
        patch(
            "api.routers.user_auth._send_verification_email",
            new=AsyncMock(return_value=True),
        ) as send_mock,
    ):
        response = await client.post(
            "/v1/user/auth/resend-verification/by-email",
            json={"email": "user@test.local"},
        )

    assert response.status_code == 200
    assert "if your account exists" in response.json()["detail"].lower()
    token_mock.assert_awaited_once()
    send_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_resend_verification_by_email_is_generic_for_unknown_user(client: AsyncClient, mock_db):
    mock_db.execute.return_value = _scalar_first_result(None)

    with (
        patch(
            "api.routers.user_auth._generate_verification_token",
            new=AsyncMock(return_value="token-123"),
        ) as token_mock,
        patch(
            "api.routers.user_auth._send_verification_email",
            new=AsyncMock(return_value=True),
        ) as send_mock,
    ):
        response = await client.post(
            "/v1/user/auth/resend-verification/by-email",
            json={"email": "unknown@test.local"},
        )

    assert response.status_code == 200
    assert "if your account exists" in response.json()["detail"].lower()
    token_mock.assert_not_awaited()
    send_mock.assert_not_awaited()
