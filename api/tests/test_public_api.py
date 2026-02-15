"""Tests for public API."""
from datetime import date, datetime, timezone
from unittest.mock import MagicMock
import uuid

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_reading_today_includes_normalized_extended_payload(client: AsyncClient, mock_db):
    reading = MagicMock()
    reading.date_context = date(2026, 2, 14)
    reading.published_standard = {"title": "Daily Reading", "body": "Body", "word_count": 510}
    reading.generated_standard = {}
    reading.published_extended = {
        "title": "Expanded Reading",
        "subtitle": "Long-form",
        "sections": [{"heading": "Section A", "body": "Expanded section body"}],
        "word_count": 1400,
    }
    reading.generated_extended = {"title": "", "subtitle": "", "sections": [], "word_count": 0}
    reading.published_annotations = [{"aspect": "Sun trine Moon"}]
    reading.generated_annotations = []
    reading.published_at = datetime(2026, 2, 14, 10, 0, tzinfo=timezone.utc)

    run = MagicMock()
    run.reused_artifacts = {"trigger_source": "scheduler"}
    db_result = MagicMock()
    db_result.all.return_value = [(reading, run)]
    mock_db.execute.return_value = db_result

    response = await client.get("/v1/reading/today")
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Daily Reading"
    assert body["has_extended"] is True
    assert body["extended"]["title"] == "Expanded Reading"
    assert body["extended"]["subtitle"] == "Long-form"
    assert body["extended"]["word_count"] == 1400
    assert body["extended"]["sections"][0]["heading"] == "Section A"
    assert body["annotations"][0]["aspect"] == "Sun trine Moon"


@pytest.mark.asyncio
async def test_reading_by_date_reports_no_extended_when_content_is_empty(client: AsyncClient, mock_db):
    reading = MagicMock()
    reading.date_context = date(2026, 2, 14)
    reading.published_standard = {"title": "Daily Reading", "body": "Body", "word_count": 500}
    reading.generated_standard = {}
    reading.published_extended = {}
    reading.generated_extended = {"title": "", "subtitle": "", "sections": [], "word_count": 0}
    reading.published_annotations = None
    reading.generated_annotations = []
    reading.published_at = None

    run = MagicMock()
    run.reused_artifacts = {"trigger_source": "scheduler"}
    db_result = MagicMock()
    db_result.all.return_value = [(reading, run)]
    mock_db.execute.return_value = db_result

    response = await client.get("/v1/reading/2026-02-14")
    assert response.status_code == 200
    body = response.json()
    assert body["has_extended"] is False
    assert body["extended"]["sections"] == []
    assert body["extended"]["word_count"] == 0


@pytest.mark.asyncio
async def test_reading_today_skips_event_triggered_readings(client: AsyncClient, mock_db):
    event_reading = MagicMock()
    event_reading.date_context = date(2026, 2, 14)
    event_reading.published_standard = {"title": "Event Reading", "body": "Event body", "word_count": 450}
    event_reading.generated_standard = {}
    event_reading.published_extended = {}
    event_reading.generated_extended = {}
    event_reading.published_annotations = []
    event_reading.generated_annotations = []
    event_reading.published_at = datetime(2026, 2, 14, 10, 0, tzinfo=timezone.utc)

    normal_reading = MagicMock()
    normal_reading.date_context = date(2026, 2, 14)
    normal_reading.published_standard = {"title": "Daily Reading", "body": "Daily body", "word_count": 500}
    normal_reading.generated_standard = {}
    normal_reading.published_extended = {}
    normal_reading.generated_extended = {}
    normal_reading.published_annotations = []
    normal_reading.generated_annotations = []
    normal_reading.published_at = datetime(2026, 2, 14, 11, 0, tzinfo=timezone.utc)

    event_run = MagicMock()
    event_run.reused_artifacts = {"trigger_source": "manual_event"}
    scheduler_run = MagicMock()
    scheduler_run.reused_artifacts = {"trigger_source": "scheduler"}

    db_result = MagicMock()
    db_result.all.return_value = [
        (event_reading, event_run),
        (normal_reading, scheduler_run),
    ]
    mock_db.execute.return_value = db_result

    response = await client.get("/v1/reading/today")
    assert response.status_code == 200
    assert response.json()["title"] == "Daily Reading"


@pytest.mark.asyncio
async def test_events_list_includes_event_reading_link(client: AsyncClient, mock_db):
    event_id = uuid.uuid4()
    run_id = uuid.uuid4()

    event = MagicMock()
    event.id = event_id
    event.event_type = "full_moon"
    event.body = "Moon"
    event.sign = "Virgo"
    event.at = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
    event.significance = "major"
    event.reading_status = "generated"
    event.reading_title = None
    event.run_id = run_id

    reading = MagicMock()
    reading.run_id = run_id
    reading.status = "pending"
    reading.published_standard = None
    reading.generated_standard = {"title": "Event Thread", "body": "Body", "word_count": 420}

    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [event]
    reading_result = MagicMock()
    reading_result.scalars.return_value.all.return_value = [reading]
    mock_db.execute.side_effect = [events_result, reading_result]

    response = await client.get("/v1/events")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["reading_available"] is True
    assert body[0]["reading_url"] == f"/events/{event_id}"
    assert body[0]["reading_title"] == "Event Thread"


@pytest.mark.asyncio
async def test_content_about_returns_default_payload(client: AsyncClient):
    response = await client.get("/v1/content/about")
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "about"
    assert body["title"] == "About"
    assert len(body["sections"]) >= 1


@pytest.mark.asyncio
async def test_content_unknown_slug_returns_404(client: AsyncClient):
    response = await client.get("/v1/content/not-a-page")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_site_config_endpoint(client: AsyncClient):
    response = await client.get("/v1/site/config")
    assert response.status_code == 200
    body = response.json()
    assert "site_title" in body
    assert "site_url" in body
    assert "tracking_head" in body
