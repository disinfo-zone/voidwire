"""Tests for public API."""
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

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

    db_result = MagicMock()
    db_result.scalars.return_value.first.return_value = reading
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

    db_result = MagicMock()
    db_result.scalars.return_value.first.return_value = reading
    mock_db.execute.return_value = db_result

    response = await client.get("/v1/reading/2026-02-14")
    assert response.status_code == 200
    body = response.json()
    assert body["has_extended"] is False
    assert body["extended"]["sections"] == []
    assert body["extended"]["word_count"] == 0


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
