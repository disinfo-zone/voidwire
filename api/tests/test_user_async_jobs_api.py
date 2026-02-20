"""Tests for user personal-reading async job endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
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
        is_test_user=False,
        is_admin_user=False,
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
    enqueue_mock = AsyncMock(return_value=fake)
    with (
        patch("api.routers.user_readings.get_user_tier", new=AsyncMock(return_value="pro")),
        patch(
            "api.routers.user_readings.enqueue_personal_reading_job",
            new=enqueue_mock,
        ),
    ):
        response = await user_client.post("/v1/user/readings/personal/jobs", json={"tier": "auto"})
    assert response.status_code == 200
    assert response.json()["job_type"] == "personal_reading.generate"
    assert enqueue_mock.await_args.kwargs["force_refresh"] is False


@pytest.mark.asyncio
async def test_enqueue_personal_job_force_refresh_allowed_for_test_user(
    user_client: AsyncClient,
    public_user,
):
    public_user.is_test_user = True
    fake = _fake_job()
    enqueue_mock = AsyncMock(return_value=fake)
    with (
        patch("api.routers.user_readings.get_user_tier", new=AsyncMock(return_value="pro")),
        patch(
            "api.routers.user_readings.enqueue_personal_reading_job",
            new=enqueue_mock,
        ),
    ):
        response = await user_client.post(
            "/v1/user/readings/personal/jobs",
            json={"tier": "auto", "force_refresh": True},
        )
    assert response.status_code == 200
    assert enqueue_mock.await_args.kwargs["force_refresh"] is True


@pytest.mark.asyncio
async def test_enqueue_personal_job_force_refresh_rejected_for_regular_user(
    user_client: AsyncClient,
):
    response = await user_client.post(
        "/v1/user/readings/personal/jobs",
        json={"tier": "auto", "force_refresh": True},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_enqueue_personal_job_rejects_pro_tier_for_free_user(user_client: AsyncClient):
    with patch("api.routers.user_readings.get_user_tier", new=AsyncMock(return_value="free")):
        response = await user_client.post("/v1/user/readings/personal/jobs", json={"tier": "pro"})
    assert response.status_code == 403


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


@pytest.mark.asyncio
async def test_get_current_personal_reading_returns_404_when_missing(user_client: AsyncClient, mock_db):
    empty = MagicMock()
    empty.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = empty
    with patch("api.routers.user_readings.get_user_tier", new=AsyncMock(return_value="pro")):
        response = await user_client.get("/v1/user/readings/personal/current")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_current_personal_reading_rejects_pro_tier_for_free_user(user_client: AsyncClient):
    with patch("api.routers.user_readings.get_user_tier", new=AsyncMock(return_value="free")):
        response = await user_client.get("/v1/user/readings/personal/current?tier=pro")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_current_personal_reading_allows_weekly_for_pro_user(user_client: AsyncClient, mock_db):
    today = date.today()
    fake_reading = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        tier="free",
        date_context=today,
        content={
            "title": "Weekly",
            "body": "Body",
            "sections": [],
            "word_count": 420,
            "transit_highlights": [],
        },
        house_system_used="placidus",
        created_at=datetime(2026, 2, 16, tzinfo=UTC),
    )
    db_result = MagicMock()
    db_result.scalars.return_value.all.return_value = [fake_reading]
    mock_db.execute.return_value = db_result
    with patch("api.routers.user_readings.get_user_tier", new=AsyncMock(return_value="pro")):
        response = await user_client.get("/v1/user/readings/personal/current?tier=free")
    assert response.status_code == 200
    assert response.json()["tier"] == "free"


@pytest.mark.asyncio
async def test_get_current_personal_reading_includes_week_coverage(user_client: AsyncClient, mock_db):
    today = date.today()
    fake_reading = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        tier="free",
        date_context=today,
        content={
            "title": "Weekly",
            "body": "Body",
            "sections": [],
            "word_count": 420,
            "transit_highlights": [],
        },
        house_system_used="placidus",
        created_at=datetime(2026, 2, 16, tzinfo=UTC),
    )
    db_result = MagicMock()
    db_result.scalars.return_value.all.return_value = [fake_reading]
    mock_db.execute.return_value = db_result
    with patch("api.routers.user_readings.get_user_tier", new=AsyncMock(return_value="free")):
        response = await user_client.get("/v1/user/readings/personal/current")
    assert response.status_code == 200
    body = response.json()
    expected_start = (today - timedelta(days=today.weekday())).isoformat()
    expected_end = (today - timedelta(days=today.weekday()) + timedelta(days=6)).isoformat()
    assert body["coverage_start"] == expected_start
    assert body["coverage_end"] == expected_end


@pytest.mark.asyncio
async def test_get_current_personal_reading_hides_template_for_regular_user(
    user_client: AsyncClient,
    mock_db,
):
    today = date.today()
    fake_reading = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        tier="free",
        date_context=today,
        content={
            "title": "Weekly",
            "body": "Body",
            "sections": [],
            "word_count": 420,
            "transit_highlights": [],
        },
        generation_metadata={"template_version": "starter_personal_reading_free.v3"},
        house_system_used="placidus",
        created_at=datetime(2026, 2, 16, tzinfo=UTC),
    )
    db_result = MagicMock()
    db_result.scalars.return_value.all.return_value = [fake_reading]
    mock_db.execute.return_value = db_result
    with (
        patch("api.routers.user_readings.get_user_tier", new=AsyncMock(return_value="free")),
        patch(
            "api.routers.user_readings._can_force_refresh_reading",
            new=AsyncMock(return_value=False),
        ),
    ):
        response = await user_client.get("/v1/user/readings/personal/current")
    assert response.status_code == 200
    body = response.json()
    assert "template_version" not in body


@pytest.mark.asyncio
async def test_get_current_personal_reading_includes_template_for_admin_test_user(
    user_client: AsyncClient,
    mock_db,
):
    today = date.today()
    fake_reading = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        tier="free",
        date_context=today,
        content={
            "title": "Weekly",
            "body": "Body",
            "sections": [],
            "word_count": 420,
            "transit_highlights": [],
        },
        generation_metadata={"template_version": "starter_personal_reading_free.v3"},
        house_system_used="placidus",
        created_at=datetime(2026, 2, 16, tzinfo=UTC),
    )
    db_result = MagicMock()
    db_result.scalars.return_value.all.return_value = [fake_reading]
    mock_db.execute.return_value = db_result
    with (
        patch("api.routers.user_readings.get_user_tier", new=AsyncMock(return_value="free")),
        patch(
            "api.routers.user_readings._can_force_refresh_reading",
            new=AsyncMock(return_value=True),
        ),
    ):
        response = await user_client.get("/v1/user/readings/personal/current")
    assert response.status_code == 200
    body = response.json()
    assert body["template_version"] == "starter_personal_reading_free.v3"
