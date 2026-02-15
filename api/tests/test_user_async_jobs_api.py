"""Tests for user personal-reading async job endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from api.dependencies import get_current_public_user, get_db
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def public_user():
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="jobs@test.local",
        is_active=True,
        profile=SimpleNamespace(),
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


def _fake_job() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        job_type="personal_reading.generate",
        status="queued",
        payload={"tier": "pro", "target_date": "2026-02-15"},
        result=None,
        error_message=None,
        attempts=0,
        created_at=datetime(2026, 2, 15, tzinfo=UTC),
        started_at=None,
        finished_at=None,
    )


@pytest.mark.asyncio
async def test_enqueue_personal_job(user_client: AsyncClient):
    fake = _fake_job()
    with (
        patch("api.routers.user_readings.get_user_tier", new=AsyncMock(return_value="pro")),
        patch(
            "api.routers.user_readings.enqueue_personal_reading_job",
            new=AsyncMock(return_value=fake),
        ),
    ):
        response = await user_client.post("/v1/user/readings/personal/jobs", json={"tier": "auto"})
    assert response.status_code == 200
    assert response.json()["job_type"] == "personal_reading.generate"


@pytest.mark.asyncio
async def test_get_personal_job_invalid_uuid_returns_404(user_client: AsyncClient):
    response = await user_client.get("/v1/user/readings/personal/jobs/not-a-uuid")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_personal_jobs(user_client: AsyncClient, mock_db):
    fake = _fake_job()
    db_result = MagicMock()
    db_result.scalars.return_value.all.return_value = [fake]
    mock_db.execute.return_value = db_result
    response = await user_client.get("/v1/user/readings/personal/jobs")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload[0]["id"] == str(fake.id)
