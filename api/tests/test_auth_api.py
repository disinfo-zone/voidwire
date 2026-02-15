"""Tests for admin auth endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from api.middleware.auth import create_access_token
from httpx import AsyncClient
from voidwire.models import AdminUser


class TestAdminAuth:
    async def test_login_invalid_credentials(self, client: AsyncClient):
        resp = await client.post(
            "/admin/auth/login",
            json={"email": "admin@test.local", "password": "bad", "totp_code": "000000"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    async def test_login_success(self, client: AsyncClient, mock_db):
        fake_user = MagicMock()
        fake_user.id = "user-id"
        fake_user.email = "admin@test.local"
        fake_user.is_active = True
        fake_user.password_hash = "hashed"
        fake_user.totp_secret = "encrypted-secret"

        db_result = MagicMock()
        db_result.scalars.return_value.first.return_value = fake_user
        mock_db.execute.return_value = db_result

        with (
            patch("api.routers.admin_auth.verify_password", return_value=True),
            patch("api.routers.admin_auth.decrypt_value", return_value="totp-secret"),
            patch("api.routers.admin_auth.pyotp.TOTP") as totp_cls,
            patch("api.routers.admin_auth.create_access_token", return_value="jwt-token"),
        ):
            totp_cls.return_value.verify.return_value = True
            resp = await client.post(
                "/admin/auth/login",
                json={
                    "email": "admin@test.local",
                    "password": "ok",
                    "totp_code": "123456",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "cookie"
        assert body["detail"] == "Logged in"
        assert "set-cookie" in resp.headers
        assert "voidwire_admin_token=" in resp.headers["set-cookie"]

    async def test_login_wrong_totp(self, client: AsyncClient, mock_db):
        fake_user = MagicMock()
        fake_user.id = "user-id"
        fake_user.email = "admin@test.local"
        fake_user.is_active = True
        fake_user.password_hash = "hashed"
        fake_user.totp_secret = "encrypted-secret"

        db_result = MagicMock()
        db_result.scalars.return_value.first.return_value = fake_user
        mock_db.execute.return_value = db_result

        with (
            patch("api.routers.admin_auth.verify_password", return_value=True),
            patch("api.routers.admin_auth.decrypt_value", return_value="totp-secret"),
            patch("api.routers.admin_auth.pyotp.TOTP") as totp_cls,
        ):
            totp_cls.return_value.verify.return_value = False
            resp = await client.post(
                "/admin/auth/login",
                json={
                    "email": "admin@test.local",
                    "password": "ok",
                    "totp_code": "654321",
                },
            )

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    async def test_logout_clears_admin_cookie(self, client: AsyncClient):
        resp = await client.post("/admin/auth/logout")
        assert resp.status_code == 200
        assert "set-cookie" in resp.headers
        assert "voidwire_admin_token=" in resp.headers["set-cookie"]

    async def test_me_accepts_admin_jwt_from_cookie(self, client: AsyncClient, mock_db):
        fake_user = MagicMock()
        fake_user.id = "admin-user-id"
        fake_user.email = "admin@test.local"
        fake_user.is_active = True
        fake_user.created_at = datetime(2026, 2, 15, tzinfo=UTC)
        mock_db.get.return_value = fake_user

        token = create_access_token(user_id=fake_user.id, token_type="admin")
        resp = await client.get(
            "/admin/auth/me",
            headers={"Cookie": f"voidwire_admin_token={token}"},
        )

        assert resp.status_code == 200
        assert resp.json()["id"] == fake_user.id
        assert mock_db.get.await_args.args[0] is AdminUser
