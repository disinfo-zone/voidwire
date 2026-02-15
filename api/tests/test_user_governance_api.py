"""Tests for user governance endpoints (export, revoke sessions, delete)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from api.dependencies import get_current_public_user, get_db
from api.middleware.auth import hash_password
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def governance_user():
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="governance@test.local",
        is_active=True,
        email_verified=True,
        display_name="Governance User",
        created_at=datetime(2026, 2, 15, tzinfo=UTC),
        last_login_at=datetime(2026, 2, 15, tzinfo=UTC),
        token_version=0,
        password_hash=hash_password("current-password"),
        profile=None,
        subscriptions=[],
    )


@pytest.fixture
async def governance_client(app, mock_db, governance_user):
    async def _override_db():
        yield mock_db

    async def _override_user():
        return governance_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_public_user] = _override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_logout_all_increments_token_version(governance_client: AsyncClient, governance_user):
    response = await governance_client.post("/v1/user/auth/logout-all")
    assert response.status_code == 200
    assert governance_user.token_version == 1
    assert "voidwire_user_token=" in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_export_account_data(governance_client: AsyncClient, mock_db):
    subs_result = MagicMock()
    subs_result.scalars.return_value.all.return_value = []
    readings_result = MagicMock()
    readings_result.scalars.return_value.all.return_value = []
    mock_db.execute.side_effect = [subs_result, readings_result]

    response = await governance_client.get("/v1/user/auth/me/export")
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "governance@test.local"
    assert "exported_at" in payload


@pytest.mark.asyncio
async def test_delete_account_requires_password_for_password_user(
    governance_client: AsyncClient,
):
    response = await governance_client.request(
        "DELETE",
        "/v1/user/auth/me",
        json={"password": "wrong"},
    )
    assert response.status_code == 401
