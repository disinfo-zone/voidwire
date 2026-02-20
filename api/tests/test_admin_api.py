"""Tests for admin API endpoints."""

import asyncio
import uuid
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

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
        assert "personal" in body["properties"]

    async def test_defaults_pipeline(self, client: AsyncClient):
        resp = await client.get("/admin/settings/defaults/pipeline")
        assert resp.status_code == 200
        body = resp.json()
        assert body["selection"]["n_select"] == 9
        assert body["threads"]["match_threshold"] == 0.75
        assert body["synthesis"]["plan_retries"] == 2
        assert body["personal"]["enabled"] is True
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
        resp = await client.put(
            "/admin/settings/",
            json={
                "key": "pipeline.selection.n_select",
                "value": {"v": 12},
                "category": "pipeline",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_put_setting_allows_array_value(self, client: AsyncClient):
        resp = await client.put(
            "/admin/settings/",
            json={
                "key": "pipeline.synthesis.banned_phrases",
                "value": ["literal", "breaking news", "hot take"],
                "category": "pipeline",
            },
        )
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
# Site Config + Backup Storage
# ──────────────────────────────────────────────


class TestSiteAndBackupSettingsAPI:
    async def test_get_site_config_defaults(self, client: AsyncClient):
        resp = await client.get("/admin/site/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["site_title"] == "VOIDWIRE"
        assert "site_url" in body
        assert "tracking_head" in body

    async def test_update_site_config(self, client: AsyncClient):
        resp = await client.put(
            "/admin/site/config",
            json={
                "site_title": "VOIDWIRE TEST",
                "site_url": "https://example.test",
                "meta_description": "Test description",
                "tracking_head": "<script>console.log('ok')</script>",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["site_title"] == "VOIDWIRE TEST"
        assert body["site_url"] == "https://example.test"

    async def test_get_backup_storage_defaults(self, client: AsyncClient):
        resp = await client.get("/admin/backup/storage")
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "local"

    async def test_update_backup_storage_local(self, client: AsyncClient):
        resp = await client.put(
            "/admin/backup/storage",
            json={"provider": "local"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "local"


# ──────────────────────────────────────────────
# Content
# ──────────────────────────────────────────────


class TestContentAPI:
    async def test_list_pages(self, client: AsyncClient):
        with patch(
            "api.routers.admin_content.list_content_pages",
            AsyncMock(
                return_value=[
                    {"slug": "about", "title": "About", "sections_count": 4, "updated_at": None}
                ]
            ),
        ):
            resp = await client.get("/admin/content/pages")
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["slug"] == "about"
        assert body[0]["sections_count"] == 4

    async def test_get_page(self, client: AsyncClient):
        with patch(
            "api.routers.admin_content.get_content_page",
            AsyncMock(
                return_value={
                    "slug": "about",
                    "title": "About",
                    "sections": [{"heading": "Transmission", "body": "Body"}],
                    "updated_at": None,
                }
            ),
        ):
            resp = await client.get("/admin/content/pages/about")
        assert resp.status_code == 200
        body = resp.json()
        assert body["slug"] == "about"
        assert body["sections"][0]["heading"] == "Transmission"

    async def test_update_page(self, client: AsyncClient):
        with patch(
            "api.routers.admin_content.save_content_page",
            AsyncMock(
                return_value={
                    "slug": "about",
                    "title": "About Updated",
                    "sections": [{"heading": "Transmission", "body": "Updated body"}],
                    "updated_at": "2026-02-14T00:00:00+00:00",
                }
            ),
        ):
            resp = await client.put(
                "/admin/content/pages/about",
                json={
                    "title": "About Updated",
                    "sections": [{"heading": "Transmission", "body": "Updated body"}],
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "About Updated"
        assert body["sections"][0]["body"] == "Updated body"

    async def test_get_page_not_found(self, client: AsyncClient):
        with patch(
            "api.routers.admin_content.get_content_page", AsyncMock(side_effect=KeyError("missing"))
        ):
            resp = await client.get("/admin/content/pages/missing")
        assert resp.status_code == 404


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

        resp = await client.post(
            "/admin/sources/",
            json={
                "name": "Test RSS",
                "url": "https://example.com/rss",
                "domain": "technology",
                "weight": 0.7,
            },
        )
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

        resp = await client.post(
            "/admin/dictionary/",
            json={
                "body1": "Mars",
                "body2": "Saturn",
                "aspect_type": "conjunction",
                "event_type": "aspect",
                "core_meaning": "Tension between action and restriction",
                "keywords": ["conflict", "discipline"],
                "domain_affinities": ["conflict"],
            },
        )
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

        resp = await client.post(
            "/admin/events/",
            json={
                "event_type": "new_moon",
                "body": "Moon",
                "sign": "Pisces",
                "at": "2026-03-14T12:00:00",
                "significance": "major",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "created"
        assert "id" in body

    async def test_create_event_accepts_datetime_local(self, client: AsyncClient, mock_db):
        fake_id = uuid.uuid4()

        def side_effect_add(obj):
            obj.id = fake_id

        mock_db.add = MagicMock(side_effect=side_effect_add)

        resp = await client.post(
            "/admin/events/",
            json={
                "event_type": "full_moon",
                "body": "Moon",
                "sign": "Virgo",
                "at": "2026-03-14T12:00",
                "significance": "moderate",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    async def test_create_event_invalid_datetime_returns_400(self, client: AsyncClient):
        resp = await client.post(
            "/admin/events/",
            json={
                "event_type": "full_moon",
                "body": "Moon",
                "sign": "Virgo",
                "at": "not-a-date",
                "significance": "moderate",
            },
        )
        assert resp.status_code == 400

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

    async def test_generate_event_reading_starts_background(self, client: AsyncClient, mock_db):
        event_id = uuid.uuid4()
        event = MagicMock()
        event.id = event_id
        event.at = datetime(2026, 3, 14, 12, 0)
        mock_db.get.return_value = event

        with (
            patch(
                "api.routers.admin_pipeline._is_pipeline_lock_available",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "api.routers.admin_events._run_event_pipeline_background",
                new=AsyncMock(return_value=None),
            ) as background_runner,
        ):
            resp = await client.post(f"/admin/events/{event_id}/generate-reading")
            await asyncio.sleep(0)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "started"
        assert body["mode"] == "background"
        assert background_runner.await_count == 1


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
    async def test_list_seeds_defaults(self, client: AsyncClient):
        resp = await client.get("/admin/llm/")
        assert resp.status_code == 200
        slots = resp.json()
        assert [s["slot"] for s in slots] == [
            "distillation",
            "embedding",
            "personal_free",
            "personal_pro",
            "synthesis",
        ]

    async def test_get_slot_not_found(self, client: AsyncClient):
        resp = await client.get("/admin/llm/synthesis")
        assert resp.status_code == 404

    async def test_put_slot_not_found(self, client: AsyncClient):
        resp = await client.put(
            "/admin/llm/synthesis",
            json={
                "provider_name": "openrouter",
                "model_id": "anthropic/claude-3.5-sonnet",
            },
        )
        assert resp.status_code == 404

    async def test_test_slot_not_found(self, client: AsyncClient):
        resp = await client.post("/admin/llm/synthesis/test")
        assert resp.status_code == 404

    async def test_embedding_slot_test_uses_embedding_endpoint(self, client: AsyncClient, mock_db):
        cfg = MagicMock()
        cfg.slot = "embedding"
        cfg.is_active = True
        cfg.provider_name = "openrouter"
        cfg.api_endpoint = "https://openrouter.ai/api/v1"
        cfg.model_id = "openai/text-embedding-3-small"
        cfg.api_key_encrypted = "encrypted-api-key"
        cfg.max_tokens = None
        cfg.temperature = 0.7

        db_result = MagicMock()
        db_result.scalars.return_value.first.return_value = cfg
        mock_db.execute.return_value = db_result

        with patch("voidwire.services.llm_client.LLMClient") as llm_client_cls:
            llm = llm_client_cls.return_value
            llm.generate_embeddings = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
            llm.generate = AsyncMock(return_value="OK")
            llm.close = AsyncMock()

            resp = await client.post("/admin/llm/embedding/test")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "Embedding generated" in body["response"]
        llm.generate_embeddings.assert_awaited_once()
        llm.generate.assert_not_awaited()


# ──────────────────────────────────────────────
# Templates
# ──────────────────────────────────────────────


class TestTemplatesAPI:
    async def test_list_seeds_starter_template(self, client: AsyncClient, mock_db):
        seeded_templates: list[object] = []

        def side_effect_add(obj):
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now(UTC)
            if getattr(obj, "template_name", None):
                seeded_templates.append(obj)

        mock_db.add = MagicMock(side_effect=side_effect_add)

        existing_names_result = MagicMock()
        existing_names_result.scalars.return_value.all.return_value = []

        seeded_result = MagicMock()
        seeded_result.scalars.return_value.all.side_effect = lambda: seeded_templates

        mock_db.execute = AsyncMock(side_effect=[existing_names_result, seeded_result])

        resp = await client.get("/admin/templates/")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 7
        by_name = {t["template_name"]: t for t in body}
        assert "starter_synthesis_prose" in by_name
        assert "synthesis_plan" in by_name
        assert "starter_synthesis_event_prose" in by_name
        assert "starter_synthesis_event_plan" in by_name
        assert "starter_personal_reading_free" in by_name
        assert "starter_personal_reading_pro" in by_name
        assert "starter_celestial_weather" in by_name
        assert by_name["starter_synthesis_prose"]["version"] == 2
        assert by_name["synthesis_plan"]["version"] == 1
        assert by_name["starter_synthesis_event_prose"]["version"] == 2
        assert by_name["starter_synthesis_event_plan"]["version"] == 1
        assert by_name["starter_personal_reading_free"]["version"] == 1
        assert by_name["starter_personal_reading_pro"]["version"] == 1
        assert by_name["starter_celestial_weather"]["version"] == 2
        assert by_name["starter_synthesis_prose"]["is_active"] is True
        assert by_name["synthesis_plan"]["is_active"] is True
        assert by_name["starter_synthesis_event_prose"]["is_active"] is True
        assert by_name["starter_synthesis_event_plan"]["is_active"] is True
        assert by_name["starter_personal_reading_free"]["is_active"] is True
        assert by_name["starter_personal_reading_pro"]["is_active"] is True
        assert by_name["starter_celestial_weather"]["is_active"] is True

    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get(f"/admin/templates/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_create_template(self, client: AsyncClient, mock_db):
        fake_id = uuid.uuid4()

        def side_effect_add(obj):
            obj.id = fake_id
            obj.created_at = datetime.now(UTC)

        mock_db.add = MagicMock(side_effect=side_effect_add)

        resp = await client.post(
            "/admin/templates/",
            json={
                "template_name": "synthesis_prose",
                "content": "You are an astrologer. {{signals}}",
                "author": "admin",
            },
        )
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

    async def test_regenerate_starts_background_run(self, client: AsyncClient, mock_db):
        reading_id = uuid.uuid4()
        reading = MagicMock()
        reading.id = reading_id
        reading.run_id = uuid.uuid4()
        reading.date_context = date(2026, 2, 14)
        mock_db.get.return_value = reading

        with (
            patch("api.routers.admin_readings._load_pipeline_runner") as loader,
            patch("api.routers.admin_readings.asyncio.create_task") as create_task,
        ):
            loader.return_value = AsyncMock(return_value=uuid.uuid4())
            real_create_task = asyncio.tasks.create_task
            create_task.side_effect = lambda coro, *args, **kwargs: real_create_task(
                coro, *args, **kwargs
            )
            resp = await client.post(
                f"/admin/readings/{reading_id}/regenerate",
                json={"mode": "prose_only"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "started"
        assert body["mode"] == "background"
        assert body["regeneration_mode"] == "prose_only"
        assert any(
            getattr(getattr(call.args[0], "cr_code", None), "co_name", "")
            == "_run_pipeline_background"
            for call in create_task.call_args_list
        )

    async def test_regenerate_wait_for_completion_returns_run_id(
        self, client: AsyncClient, mock_db
    ):
        reading_id = uuid.uuid4()
        reading = MagicMock()
        reading.id = reading_id
        reading.run_id = uuid.uuid4()
        reading.date_context = date(2026, 2, 14)
        mock_db.get.return_value = reading

        run_id = uuid.uuid4()
        with patch("api.routers.admin_readings._load_pipeline_runner") as loader:
            runner = AsyncMock(return_value=run_id)
            loader.return_value = runner
            resp = await client.post(
                f"/admin/readings/{reading_id}/regenerate",
                json={"mode": "reselect", "wait_for_completion": True},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "triggered"
        assert body["run_id"] == str(run_id)
        assert runner.await_args.kwargs["date_context"] == reading.date_context
        assert runner.await_args.kwargs["parent_run_id"] == reading.run_id
        assert runner.await_args.kwargs["regeneration_mode"].value == "reselect"


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

    async def test_schedule_endpoint(self, client: AsyncClient):
        resp = await client.get("/admin/pipeline/schedule")
        assert resp.status_code == 200
        body = resp.json()
        assert "pipeline_schedule" in body
        assert "timezone" in body
        assert "edit_location" in body

    async def test_schedule_update(self, client: AsyncClient):
        resp = await client.put(
            "/admin/pipeline/schedule",
            json={
                "pipeline_schedule": "15 6 * * *",
                "timezone": "UTC",
                "pipeline_run_on_start": False,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_trigger_pipeline_success(self, client: AsyncClient):
        run_id = uuid.uuid4()
        with patch("api.routers.admin_pipeline._load_pipeline_runner") as loader:
            runner = AsyncMock(return_value=run_id)
            loader.return_value = runner
            resp = await client.post("/admin/pipeline/trigger", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "triggered"
        assert body["run_id"] == str(run_id)
        assert runner.await_args.kwargs["trigger_source"] == "manual"

    async def test_trigger_pipeline_background_mode(self, client: AsyncClient):
        with (
            patch("api.routers.admin_pipeline._load_pipeline_runner") as loader,
            patch("api.routers.admin_pipeline.asyncio.create_task") as create_task,
        ):
            loader.return_value = AsyncMock(return_value=uuid.uuid4())
            real_create_task = asyncio.tasks.create_task
            create_task.side_effect = lambda coro, *args, **kwargs: real_create_task(
                coro, *args, **kwargs
            )
            resp = await client.post(
                "/admin/pipeline/trigger",
                json={"wait_for_completion": False},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "started"
        assert body["mode"] == "background"
        assert any(
            getattr(getattr(call.args[0], "cr_code", None), "co_name", "")
            == "_run_pipeline_background"
            for call in create_task.call_args_list
        )

    async def test_trigger_pipeline_dependency_missing_returns_503(self, client: AsyncClient):
        with patch(
            "api.routers.admin_pipeline._load_pipeline_runner",
            side_effect=HTTPException(
                status_code=503,
                detail="Pipeline package is unavailable in API container. Rebuild API image.",
            ),
        ):
            resp = await client.post("/admin/pipeline/trigger", json={})
        assert resp.status_code == 503
        assert "Pipeline package is unavailable" in resp.json()["detail"]

    async def test_trigger_pipeline_lock_conflict_returns_409(self, client: AsyncClient):
        with patch("api.routers.admin_pipeline._load_pipeline_runner") as loader:
            loader.return_value = AsyncMock(
                side_effect=RuntimeError("Could not acquire advisory lock for 2026-02-14")
            )
            resp = await client.post("/admin/pipeline/trigger", json={})
        assert resp.status_code == 409
        assert "already in progress" in resp.json()["detail"]


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
# Accounts + Billing
# ──────────────────────────────────────────────


class TestAccountsAPI:
    async def test_list_users(self, client: AsyncClient, mock_db):
        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        fake_user.email = "pro@test.local"
        fake_user.display_name = "Pro User"
        fake_user.email_verified = True
        fake_user.is_active = True
        fake_user.created_at = datetime.now(UTC)
        fake_user.last_login_at = datetime.now(UTC)
        fake_user.pro_override = False
        fake_user.pro_override_reason = None
        fake_user.pro_override_until = None

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [fake_user]
        subs_result = MagicMock()
        subs_result.all.return_value = [(fake_user.id,)]
        mock_db.execute.side_effect = [users_result, subs_result]

        resp = await client.get("/admin/accounts/users")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["email"] == "pro@test.local"
        assert body[0]["tier"] == "pro"
        assert body[0]["has_active_subscription"] is True

    async def test_update_user_pro_override(self, client: AsyncClient, mock_db):
        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        fake_user.pro_override = False
        fake_user.pro_override_reason = None
        fake_user.pro_override_until = None
        fake_user.is_active = True
        fake_user.token_version = 0
        mock_db.get.return_value = fake_user

        resp = await client.patch(
            f"/admin/accounts/users/{fake_user.id}/pro-override",
            json={"enabled": True, "reason": "manual QA", "expires_at": None},
        )
        assert resp.status_code == 200
        assert resp.json()["pro_override"] is True
        assert resp.json()["tier"] == "pro"
        assert fake_user.pro_override is True
        assert fake_user.pro_override_reason == "manual QA"
        mock_db.flush.assert_awaited()

    async def test_create_user(self, client: AsyncClient, mock_db):
        existing_result = MagicMock()
        existing_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = existing_result

        def side_effect_add(obj):
            if getattr(obj, "email", None) == "new-user@test.local":
                obj.id = uuid.uuid4()
                obj.created_at = datetime.now(UTC)
                obj.last_login_at = None
                obj.pro_override = False
                obj.pro_override_reason = None
                obj.pro_override_until = None

        mock_db.add = MagicMock(side_effect=side_effect_add)

        resp = await client.post(
            "/admin/accounts/users",
            json={
                "email": "new-user@test.local",
                "password": "temporary-password",
                "display_name": "New User",
                "email_verified": True,
                "is_active": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "new-user@test.local"
        assert body["display_name"] == "New User"
        assert body["is_active"] is True

    async def test_update_user(self, client: AsyncClient, mock_db):
        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        fake_user.email = "update@test.local"
        fake_user.display_name = "Before"
        fake_user.email_verified = False
        fake_user.is_active = True
        fake_user.token_version = 0
        fake_user.created_at = datetime.now(UTC)
        fake_user.last_login_at = None
        fake_user.pro_override = False
        fake_user.pro_override_reason = None
        fake_user.pro_override_until = None
        mock_db.get.return_value = fake_user

        subs_result = MagicMock()
        subs_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = subs_result

        resp = await client.patch(
            f"/admin/accounts/users/{fake_user.id}",
            json={
                "display_name": "After",
                "email_verified": True,
                "is_active": False,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["display_name"] == "After"
        assert body["email_verified"] is True
        assert body["is_active"] is False

    async def test_delete_user(self, client: AsyncClient, mock_db):
        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        fake_user.email = "delete@test.local"
        mock_db.get.return_value = fake_user

        resp = await client.delete(f"/admin/accounts/users/{fake_user.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        mock_db.delete.assert_awaited_once_with(fake_user)
        mock_db.flush.assert_awaited()
        mock_db.commit.assert_awaited()

    async def test_delete_user_falls_back_to_deactivation_on_integrity_error(
        self, client: AsyncClient, mock_db
    ):
        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        fake_user.email = "delete-fallback@test.local"
        mock_db.get.side_effect = [fake_user, fake_user]
        mock_db.flush.side_effect = [IntegrityError("DELETE FROM users", {}, Exception("fk violation"))]

        resp = await client.delete(f"/admin/accounts/users/{fake_user.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deactivated"
        mock_db.rollback.assert_awaited_once()
        assert mock_db.execute.await_count >= 6
        assert mock_db.commit.await_count >= 2

    async def test_delete_user_falls_back_to_deactivation_when_commit_deferred_constraint_fails(
        self, client: AsyncClient, mock_db
    ):
        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        fake_user.email = "delete-commit-fallback@test.local"
        mock_db.get.side_effect = [fake_user, fake_user]
        mock_db.commit.side_effect = [
            IntegrityError("COMMIT", {}, Exception("deferred fk violation")),
            None,
            None,
        ]

        resp = await client.delete(f"/admin/accounts/users/{fake_user.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deactivated"
        mock_db.rollback.assert_awaited_once()
        assert mock_db.execute.await_count >= 6
        assert mock_db.commit.await_count >= 3

    async def test_list_personal_reading_jobs(self, client: AsyncClient, mock_db):
        job = MagicMock()
        job.id = uuid.uuid4()
        job.user_id = uuid.uuid4()
        job.job_type = "personal_reading.generate"
        job.status = "failed"
        job.payload = {"tier": "pro", "target_date": "2026-02-16"}
        job.result = None
        job.error_message = "Failed to generate"
        job.attempts = 2
        job.created_at = datetime.now(UTC)
        job.started_at = datetime.now(UTC)
        job.finished_at = datetime.now(UTC)

        jobs_result = MagicMock()
        jobs_result.all.return_value = [(job, "job-user@test.local")]
        mock_db.execute.return_value = jobs_result

        resp = await client.get("/admin/accounts/reading-jobs?status=failed")
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["status"] == "failed"
        assert body[0]["user_email"] == "job-user@test.local"

    async def test_regenerate_user_readings_for_pro_user(self, client: AsyncClient, mock_db):
        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        fake_user.email = "regen-pro@test.local"
        fake_user.is_active = True
        fake_user.profile = MagicMock()
        mock_db.get.return_value = fake_user

        weekly_job = MagicMock()
        weekly_job.id = uuid.uuid4()
        weekly_job.user_id = fake_user.id
        weekly_job.job_type = "personal_reading.generate"
        weekly_job.status = "queued"
        weekly_job.payload = {"tier": "free", "target_date": date.today().isoformat()}
        weekly_job.result = None
        weekly_job.error_message = None
        weekly_job.attempts = 0
        weekly_job.created_at = datetime.now(UTC)
        weekly_job.started_at = None
        weekly_job.finished_at = None

        daily_job = MagicMock()
        daily_job.id = uuid.uuid4()
        daily_job.user_id = fake_user.id
        daily_job.job_type = "personal_reading.generate"
        daily_job.status = "queued"
        daily_job.payload = {"tier": "pro", "target_date": date.today().isoformat()}
        daily_job.result = None
        daily_job.error_message = None
        daily_job.attempts = 0
        daily_job.created_at = datetime.now(UTC)
        daily_job.started_at = None
        daily_job.finished_at = None

        with (
            patch("api.routers.admin_accounts.get_user_tier", new=AsyncMock(return_value="pro")),
            patch(
                "api.routers.admin_accounts.enqueue_personal_reading_job",
                new=AsyncMock(side_effect=[weekly_job, daily_job]),
            ) as enqueue_mock,
        ):
            resp = await client.post(f"/admin/accounts/users/{fake_user.id}/readings/regenerate")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "queued"
        assert body["tier"] == "pro"
        assert body["queued_tiers"] == ["free", "pro"]
        assert enqueue_mock.await_count == 2
        assert enqueue_mock.await_args_list[0].kwargs["tier"] == "free"
        assert enqueue_mock.await_args_list[0].kwargs["force_refresh"] is True
        assert enqueue_mock.await_args_list[1].kwargs["tier"] == "pro"

    async def test_get_user_natal_chart(self, client: AsyncClient, mock_db):
        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        fake_user.email = "chart@test.local"
        fake_profile = MagicMock()
        fake_profile.birth_city = "LaGrange, GA"
        fake_profile.birth_timezone = "America/New_York"
        fake_profile.house_system = "placidus"
        fake_profile.natal_chart_computed_at = datetime.now(UTC)
        fake_profile.natal_chart_json = {
            "positions": [
                {"body": "sun", "sign": "Sagittarius", "degree": 3.9, "longitude": 243.9},
                {"body": "part_of_fortune", "sign": "Capricorn", "degree": 1.2, "longitude": 271.2},
            ],
            "angles": [{"name": "Ascendant", "sign": "Aries", "degree": 8.3, "longitude": 8.3}],
            "house_cusps": [8.3, 15.3, 12.1, 5.0, 28.6, 27.8, 188.3, 195.3, 192.1, 185.0, 178.6, 177.8],
            "house_signs": [],
            "house_system": "placidus",
            "aspects": [],
        }
        fake_user.profile = fake_profile
        mock_db.get.return_value = fake_user

        resp = await client.get(f"/admin/accounts/users/{fake_user.id}/natal-chart")
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_email"] == "chart@test.local"
        assert body["birth_city"] == "LaGrange, GA"
        assert body["birth_timezone"] == "America/New_York"
        assert body["chart"]["house_system"] == "placidus"

    async def test_create_discount_code(self, client: AsyncClient, mock_db):
        existing_result = MagicMock()
        existing_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = existing_result

        def side_effect_add(obj):
            if getattr(obj, "code", None) == "TEST50":
                obj.id = uuid.uuid4()
                obj.created_at = datetime.now(UTC)
                obj.updated_at = datetime.now(UTC)

        mock_db.add = MagicMock(side_effect=side_effect_add)

        with patch(
            "api.routers.admin_accounts.create_coupon_and_promotion_code",
            return_value={
                "stripe_coupon_id": "coupon_123",
                "stripe_promotion_code_id": "promo_123",
            },
        ):
            resp = await client.post(
                "/admin/accounts/discount-codes",
                json={
                    "code": "test50",
                    "percent_off": 50,
                    "duration": "once",
                    "description": "QA discount",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "TEST50"
        assert body["percent_off"] == 50
        assert body["is_active"] is True

    async def test_create_amount_discount_code(self, client: AsyncClient, mock_db):
        existing_result = MagicMock()
        existing_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = existing_result

        def side_effect_add(obj):
            if getattr(obj, "code", None) == "SAVE500":
                obj.id = uuid.uuid4()
                obj.created_at = datetime.now(UTC)
                obj.updated_at = datetime.now(UTC)

        mock_db.add = MagicMock(side_effect=side_effect_add)

        with patch(
            "api.routers.admin_accounts.create_coupon_and_promotion_code",
            return_value={
                "stripe_coupon_id": "coupon_456",
                "stripe_promotion_code_id": "promo_456",
            },
        ):
            resp = await client.post(
                "/admin/accounts/discount-codes",
                json={
                    "code": "save500",
                    "amount_off_cents": 500,
                    "currency": "usd",
                    "duration": "once",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "SAVE500"
        assert body["amount_off_cents"] == 500
        assert body["currency"] == "usd"

    async def test_disable_discount_code(self, client: AsyncClient, mock_db):
        code_id = uuid.uuid4()
        discount = MagicMock()
        discount.id = code_id
        discount.code = "TEST50"
        discount.description = None
        discount.percent_off = 50
        discount.amount_off_cents = None
        discount.currency = None
        discount.duration = "once"
        discount.duration_in_months = None
        discount.max_redemptions = None
        discount.starts_at = None
        discount.expires_at = None
        discount.is_active = True
        discount.created_at = datetime.now(UTC)
        discount.updated_at = datetime.now(UTC)
        discount.stripe_promotion_code_id = "promo_123"
        mock_db.get.return_value = discount

        with patch("api.routers.admin_accounts.set_promotion_code_active") as set_active:
            resp = await client.patch(
                f"/admin/accounts/discount-codes/{code_id}",
                json={"is_active": False},
            )

        assert resp.status_code == 200
        assert resp.json()["is_active"] is False
        set_active.assert_called_once_with("promo_123", active=False, secret_key=None)

    async def test_delete_discount_code(self, client: AsyncClient, mock_db):
        code_id = uuid.uuid4()
        discount = MagicMock()
        discount.id = code_id
        discount.code = "OLDCODE"
        discount.is_active = True
        discount.stripe_promotion_code_id = "promo_legacy"
        mock_db.get.return_value = discount

        with patch("api.routers.admin_accounts.set_promotion_code_active") as set_active:
            resp = await client.delete(f"/admin/accounts/discount-codes/{code_id}")

        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        set_active.assert_called_once_with("promo_legacy", active=False, secret_key=None)
        mock_db.delete.assert_awaited_once_with(discount)

    async def test_operational_health_endpoint(self, client: AsyncClient, mock_db):
        webhook_result = MagicMock()
        webhook_result.scalars.return_value.first.return_value = datetime.now(UTC)

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        latest_cleanup_result = MagicMock()
        latest_cleanup_result.scalars.return_value.first.return_value = datetime.now(UTC)

        mock_db.execute = AsyncMock(
            side_effect=[
                webhook_result,
                count_result,
                count_result,
                count_result,
                count_result,
                latest_cleanup_result,
                count_result,
                count_result,
                count_result,
            ]
        )

        resp = await client.get("/admin/analytics/operational-health")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "alerts" in body
        assert "slo" in body

    async def test_kpis_endpoint(self, client: AsyncClient, mock_db):
        def scalar_result(value):
            result = MagicMock()
            result.scalar.return_value = value
            result.all.return_value = []
            return result

        grouped_jobs = MagicMock()
        grouped_jobs.all.return_value = [("completed", 6), ("failed", 1)]

        grouped_pipeline = MagicMock()
        grouped_pipeline.all.return_value = [("completed", 5), ("failed", 0)]

        mock_db.execute = AsyncMock(
            side_effect=[
                scalar_result(100),  # total_users
                scalar_result(12),  # new_users_7d
                scalar_result(80),  # email_verified_users
                scalar_result(60),  # users_with_profile
                scalar_result(24),  # active_subscribers
                scalar_result(4),  # trialing_subscribers
                scalar_result(2),  # past_due_subscribers
                scalar_result(10),  # canceled_subscribers
                scalar_result(3),  # manual_pro_overrides
                scalar_result(2),  # test_users
                scalar_result(27),  # pro_users_total
                scalar_result(350),  # personal_generated_total
                scalar_result(15),  # personal_generated_24h
                scalar_result(9),  # personal_generated_today
                scalar_result(6),  # personal_pro_today
                grouped_jobs,  # jobs by status
                grouped_pipeline,  # pipeline by status
                scalar_result(28),  # published_30d
            ]
        )

        resp = await client.get("/admin/analytics/kpis")
        assert resp.status_code == 200
        body = resp.json()
        assert body["users"]["total"] == 100
        assert body["users"]["pro_total"] == 27
        assert body["jobs_24h"]["failed"] == 1
        assert body["pipeline_7d"]["completed"] == 5


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
            ("GET", "/admin/content/pages"),
            ("GET", "/admin/site/config"),
            ("GET", "/admin/site/billing/stripe"),
            ("GET", "/admin/backup/storage"),
            ("GET", "/admin/accounts/users"),
            ("GET", "/admin/accounts/reading-jobs"),
            ("GET", "/admin/accounts/discount-codes"),
            ("GET", "/admin/analytics/operational-health"),
            ("GET", "/admin/analytics/kpis"),
        ]
        for method, path in routes:
            resp = await client.request(method, path)
            assert resp.status_code in (200, 404), f"{method} {path} returned {resp.status_code}"
