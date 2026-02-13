"""Tests for admin API endpoints."""
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient


# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────

class TestAuth:
    async def test_unauthenticated_settings_returns_401(self, unauthenticated_client: AsyncClient):
        resp = await unauthenticated_client.get("/admin/settings/")
        assert resp.status_code == 401

    async def test_unauthenticated_sources_returns_401(self, unauthenticated_client: AsyncClient):
        resp = await unauthenticated_client.get("/admin/sources/")
        assert resp.status_code == 401

    async def test_unauthenticated_readings_returns_401(self, unauthenticated_client: AsyncClient):
        resp = await unauthenticated_client.get("/admin/readings/")
        assert resp.status_code == 401


# ──────────────────────────────────────────────
# Settings
# ──────────────────────────────────────────────

class TestSettingsAPI:
    async def test_schema_pipeline(self, client: AsyncClient):
        resp = await client.get("/admin/settings/schema/pipeline")
        assert resp.status_code == 200
        body = resp.json()
        assert "properties" in body
        assert "selection" in body["properties"]
        assert "threads" in body["properties"]
        assert "synthesis" in body["properties"]

    async def test_defaults_pipeline(self, client: AsyncClient):
        resp = await client.get("/admin/settings/defaults/pipeline")
        assert resp.status_code == 200
        body = resp.json()
        assert body["selection"]["n_select"] == 9
        assert body["threads"]["match_threshold"] == 0.75
        assert body["synthesis"]["plan_retries"] == 2
        assert body["ingestion"]["max_total"] == 80
        assert body["distillation"]["content_truncation"] == 500

    async def test_effective_pipeline_empty_db(self, client: AsyncClient):
        """With no overrides in DB, effective == defaults."""
        resp = await client.get("/admin/settings/effective/pipeline")
        assert resp.status_code == 200
        body = resp.json()
        assert body["selection"]["n_select"] == 9

    async def test_list_settings_empty(self, client: AsyncClient):
        resp = await client.get("/admin/settings/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_put_setting(self, client: AsyncClient):
        resp = await client.put("/admin/settings/", json={
            "key": "pipeline.selection.n_select",
            "value": {"v": 12},
            "category": "pipeline",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_get_setting_not_found(self, client: AsyncClient):
        resp = await client.get("/admin/settings/nonexistent.key")
        assert resp.status_code == 404

    async def test_delete_setting_not_found(self, client: AsyncClient):
        resp = await client.delete("/admin/settings/nonexistent.key")
        assert resp.status_code == 404

    async def test_reset_category(self, client: AsyncClient):
        resp = await client.post("/admin/settings/reset-category/pipeline")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "deleted_count" in body


# ──────────────────────────────────────────────
# Sources
# ──────────────────────────────────────────────

class TestSourcesAPI:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/admin/sources/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get(f"/admin/sources/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_create_source(self, client: AsyncClient, mock_db):
        # Mock flush to set the id
        fake_source = MagicMock()
        fake_source.id = uuid.uuid4()

        original_add = mock_db.add
        def side_effect_add(obj):
            obj.id = fake_source.id
            original_add(obj)

        mock_db.add = MagicMock(side_effect=side_effect_add)

        resp = await client.post("/admin/sources/", json={
            "name": "Test RSS",
            "url": "https://example.com/rss",
            "domain": "technology",
            "weight": 0.7,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "created"
        assert "id" in body

    async def test_delete_not_found(self, client: AsyncClient):
        resp = await client.delete(f"/admin/sources/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_patch_not_found(self, client: AsyncClient):
        resp = await client.patch(
            f"/admin/sources/{uuid.uuid4()}",
            json={"name": "Updated"},
        )
        assert resp.status_code == 404


# ──────────────────────────────────────────────
# Dictionary
# ──────────────────────────────────────────────

class TestDictionaryAPI:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/admin/dictionary/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_filters(self, client: AsyncClient):
        resp = await client.get("/admin/dictionary/?body1=Mars&event_type=aspect&q=conflict")
        assert resp.status_code == 200

    async def test_create_meaning(self, client: AsyncClient, mock_db):
        fake_meaning = MagicMock()
        fake_meaning.id = uuid.uuid4()

        def side_effect_add(obj):
            obj.id = fake_meaning.id

        mock_db.add = MagicMock(side_effect=side_effect_add)

        resp = await client.post("/admin/dictionary/", json={
            "body1": "Mars",
            "body2": "Saturn",
            "aspect_type": "conjunction",
            "event_type": "aspect",
            "core_meaning": "Tension between action and restriction",
            "keywords": ["conflict", "discipline"],
            "domain_affinities": ["conflict"],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "id" in body

    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get(f"/admin/dictionary/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_delete_not_found(self, client: AsyncClient):
        resp = await client.delete(f"/admin/dictionary/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_bulk_import(self, client: AsyncClient, mock_db):
        fake_id = uuid.uuid4()

        def side_effect_add(obj):
            obj.id = fake_id

        mock_db.add = MagicMock(side_effect=side_effect_add)

        entries = [
            {
                "body1": "Venus",
                "event_type": "ingress",
                "core_meaning": "Beauty entering new domain",
            },
            {
                "body1": "Jupiter",
                "event_type": "retrograde",
                "core_meaning": "Expansion revisited",
            },
        ]
        resp = await client.post("/admin/dictionary/bulk-import", json=entries)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["count"] == 2


# ──────────────────────────────────────────────
# Events
# ──────────────────────────────────────────────

class TestEventsAPI:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/admin/events/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_event(self, client: AsyncClient, mock_db):
        fake_id = uuid.uuid4()

        def side_effect_add(obj):
            obj.id = fake_id

        mock_db.add = MagicMock(side_effect=side_effect_add)

        resp = await client.post("/admin/events/", json={
            "event_type": "new_moon",
            "body": "Moon",
            "sign": "Pisces",
            "at": "2026-03-14T12:00:00",
            "significance": "major",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "created"
        assert "id" in body

    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get(f"/admin/events/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_delete_not_found(self, client: AsyncClient):
        resp = await client.delete(f"/admin/events/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_patch_not_found(self, client: AsyncClient):
        resp = await client.patch(
            f"/admin/events/{uuid.uuid4()}",
            json={"significance": "minor"},
        )
        assert resp.status_code == 404


# ──────────────────────────────────────────────
# Threads
# ──────────────────────────────────────────────

class TestThreadsAPI:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/admin/threads/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_filters(self, client: AsyncClient):
        resp = await client.get("/admin/threads/?active=true&domain=economy")
        assert resp.status_code == 200

    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get(f"/admin/threads/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_patch_not_found(self, client: AsyncClient):
        resp = await client.patch(
            f"/admin/threads/{uuid.uuid4()}",
            json={"canonical_summary": "Updated summary"},
        )
        assert resp.status_code == 404

    async def test_delete_not_found(self, client: AsyncClient):
        resp = await client.delete(f"/admin/threads/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_signals_not_found(self, client: AsyncClient):
        resp = await client.get(f"/admin/threads/{uuid.uuid4()}/signals")
        assert resp.status_code == 404


# ──────────────────────────────────────────────
# Signals
# ──────────────────────────────────────────────

class TestSignalsAPI:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/admin/signals/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_filters(self, client: AsyncClient):
        resp = await client.get(
            "/admin/signals/?date_from=2026-01-01&date_to=2026-03-01&domain=economy&intensity=major&selected_only=true"
        )
        assert resp.status_code == 200

    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get("/admin/signals/test-signal-id")
        assert resp.status_code == 404

    async def test_stats(self, client: AsyncClient, mock_db):
        # Mock: by_domain returns one row, by_intensity returns one row, total returns 5
        domain_result = MagicMock()
        domain_result.all.return_value = [("economy", 3)]

        intensity_result = MagicMock()
        intensity_result.all.return_value = [("major", 2)]

        total_result = MagicMock()
        total_result.scalar.return_value = 5

        mock_db.execute = AsyncMock(side_effect=[domain_result, intensity_result, total_result])

        resp = await client.get("/admin/signals/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "by_domain" in body
        assert "by_intensity" in body


# ──────────────────────────────────────────────
# LLM Config
# ──────────────────────────────────────────────

class TestLLMConfigAPI:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/admin/llm/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_slot_not_found(self, client: AsyncClient):
        resp = await client.get("/admin/llm/synthesis")
        assert resp.status_code == 404

    async def test_put_slot_not_found(self, client: AsyncClient):
        resp = await client.put("/admin/llm/synthesis", json={
            "provider_name": "openrouter",
            "model_id": "anthropic/claude-3.5-sonnet",
        })
        assert resp.status_code == 404

    async def test_test_slot_not_found(self, client: AsyncClient):
        resp = await client.post("/admin/llm/synthesis/test")
        assert resp.status_code == 404


# ──────────────────────────────────────────────
# Templates
# ──────────────────────────────────────────────

class TestTemplatesAPI:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/admin/templates/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get(f"/admin/templates/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_create_template(self, client: AsyncClient, mock_db):
        fake_id = uuid.uuid4()

        def side_effect_add(obj):
            obj.id = fake_id
            obj.created_at = datetime.now(timezone.utc)

        mock_db.add = MagicMock(side_effect=side_effect_add)

        resp = await client.post("/admin/templates/", json={
            "template_name": "synthesis_prose",
            "content": "You are an astrologer. {{signals}}",
            "author": "admin",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "id" in body

    async def test_rollback_not_found(self, client: AsyncClient):
        resp = await client.post(f"/admin/templates/{uuid.uuid4()}/rollback", json={})
        assert resp.status_code == 404


# ──────────────────────────────────────────────
# Readings
# ──────────────────────────────────────────────

class TestReadingsAPI:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/admin/readings/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get(f"/admin/readings/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_diff_not_found(self, client: AsyncClient):
        resp = await client.get(f"/admin/readings/{uuid.uuid4()}/diff")
        assert resp.status_code == 404

    async def test_signals_not_found(self, client: AsyncClient):
        resp = await client.get(f"/admin/readings/{uuid.uuid4()}/signals")
        assert resp.status_code == 404

    async def test_content_patch_not_found(self, client: AsyncClient):
        resp = await client.patch(
            f"/admin/readings/{uuid.uuid4()}/content",
            json={"published_standard": {"title": "Updated", "body": "New text"}},
        )
        assert resp.status_code == 404


# ──────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────

class TestPipelineAPI:
    async def test_list_runs_empty(self, client: AsyncClient):
        resp = await client.get("/admin/pipeline/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_artifacts_not_found(self, client: AsyncClient):
        resp = await client.get(f"/admin/pipeline/runs/{uuid.uuid4()}/artifacts")
        assert resp.status_code == 404


# ──────────────────────────────────────────────
# Audit
# ──────────────────────────────────────────────

class TestAuditAPI:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/admin/audit/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_filters(self, client: AsyncClient):
        resp = await client.get(
            "/admin/audit/?action=source.create&target_type=source&date_from=2026-01-01&date_to=2026-03-01"
        )
        assert resp.status_code == 200


# ──────────────────────────────────────────────
# Route registration
# ──────────────────────────────────────────────

class TestRouteRegistration:
    """Verify all admin routers are mounted at the expected prefixes."""

    async def test_all_admin_routes_accessible(self, client: AsyncClient):
        """Each admin section responds (200 or 404) rather than 405 or unmatched."""
        routes = [
            ("GET", "/admin/settings/"),
            ("GET", "/admin/settings/schema/pipeline"),
            ("GET", "/admin/settings/defaults/pipeline"),
            ("GET", "/admin/sources/"),
            ("GET", "/admin/templates/"),
            ("GET", "/admin/dictionary/"),
            ("GET", "/admin/readings/"),
            ("GET", "/admin/pipeline/runs"),
            ("GET", "/admin/events/"),
            ("GET", "/admin/audit/"),
            ("GET", "/admin/llm/"),
            ("GET", "/admin/threads/"),
            ("GET", "/admin/signals/"),
            ("GET", "/admin/signals/stats"),
        ]
        for method, path in routes:
            resp = await client.request(method, path)
            assert resp.status_code in (200, 404), f"{method} {path} returned {resp.status_code}"
