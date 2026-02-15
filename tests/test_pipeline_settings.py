"""Tests for PipelineSettings service -- Pydantic models, defaults, schema, and merging."""

from voidwire.services.pipeline_settings import (
    DistillationSettings,
    IngestionSettings,
    PipelineSettings,
    SelectionSettings,
    SynthesisSettings,
    ThreadSettings,
    load_pipeline_settings,
    pipeline_settings_schema,
)

# ---------- Default values ----------


class TestSelectionSettingsDefaults:
    def test_defaults(self):
        s = SelectionSettings()
        assert s.n_select == 9
        assert s.n_wild == 1
        assert s.diversity_bonus == 1.5
        assert s.quality_floor == 0.5
        assert s.min_text_length == 20

    def test_intensity_scores_defaults(self):
        s = SelectionSettings()
        assert s.intensity_scores == {"major": 3.0, "moderate": 2.0, "minor": 1.0}

    def test_wild_card_excluded_domains(self):
        s = SelectionSettings()
        assert s.wild_card_excluded_domains == ["anomalous", "health"]

    def test_override(self):
        s = SelectionSettings(n_select=5, quality_floor=0.8)
        assert s.n_select == 5
        assert s.quality_floor == 0.8
        assert s.n_wild == 1  # unchanged default


class TestThreadSettingsDefaults:
    def test_defaults(self):
        t = ThreadSettings()
        assert t.match_threshold == 0.75
        assert t.summary_update_threshold == 0.92
        assert t.centroid_decay == 0.8
        assert t.deactivation_days == 7
        assert t.domain_bonus == 0.1
        assert t.reactivation_multiplier == 3

    def test_override(self):
        t = ThreadSettings(match_threshold=0.85, deactivation_days=14)
        assert t.match_threshold == 0.85
        assert t.deactivation_days == 14


class TestSynthesisSettingsDefaults:
    def test_defaults(self):
        s = SynthesisSettings()
        assert s.plan_retries == 2
        assert s.prose_retries == 3
        assert s.plan_temp_start == 0.7
        assert s.plan_temp_step == 0.15
        assert s.prose_temp_start == 0.7
        assert s.prose_temp_step == 0.1
        assert s.prose_temp_min == 0.5
        assert s.fallback_temp == 0.6

    def test_word_ranges(self):
        s = SynthesisSettings()
        assert s.standard_word_range == [400, 600]
        assert s.extended_word_range == [1200, 1800]
        assert s.signal_display_limit == 12

    def test_banned_phrases(self):
        s = SynthesisSettings()
        assert "buckle up" in s.banned_phrases
        assert "wild ride" in s.banned_phrases
        assert len(s.banned_phrases) >= 5

    def test_override_word_range(self):
        s = SynthesisSettings(standard_word_range=[300, 500])
        assert s.standard_word_range == [300, 500]
        assert s.extended_word_range == [1200, 1800]  # default preserved


class TestIngestionSettingsDefaults:
    def test_defaults(self):
        s = IngestionSettings()
        assert s.max_per_domain == 15
        assert s.max_total == 80
        assert s.fulltext_timeout == 5.0
        assert s.rss_timeout == 15.0


class TestDistillationSettingsDefaults:
    def test_defaults(self):
        d = DistillationSettings()
        assert d.content_truncation == 500
        assert d.target_signals_min == 15
        assert d.target_signals_max == 20


# ---------- PipelineSettings composite ----------


class TestPipelineSettings:
    def test_all_submodels_present(self):
        ps = PipelineSettings()
        assert isinstance(ps.selection, SelectionSettings)
        assert isinstance(ps.threads, ThreadSettings)
        assert isinstance(ps.synthesis, SynthesisSettings)
        assert isinstance(ps.ingestion, IngestionSettings)
        assert isinstance(ps.distillation, DistillationSettings)

    def test_model_dump_roundtrip(self):
        ps = PipelineSettings()
        dump = ps.model_dump()
        restored = PipelineSettings(**dump)
        assert restored == ps

    def test_partial_override(self):
        ps = PipelineSettings(selection=SelectionSettings(n_select=5))
        assert ps.selection.n_select == 5
        assert ps.threads.match_threshold == 0.75  # default

    def test_nested_override_via_dict(self):
        """Simulates how load_pipeline_settings merges overrides."""
        defaults = PipelineSettings()
        merged = defaults.model_dump()
        merged["selection"]["n_select"] = 12
        merged["synthesis"]["plan_retries"] = 5
        ps = PipelineSettings(**merged)
        assert ps.selection.n_select == 12
        assert ps.synthesis.plan_retries == 5
        # Unchanged defaults preserved
        assert ps.selection.n_wild == 1
        assert ps.threads.deactivation_days == 7


# ---------- JSON Schema ----------


class TestPipelineSettingsSchema:
    def test_schema_returns_dict(self):
        schema = pipeline_settings_schema()
        assert isinstance(schema, dict)

    def test_schema_has_required_sections(self):
        schema = pipeline_settings_schema()
        assert "properties" in schema
        props = schema["properties"]
        assert "selection" in props
        assert "threads" in props
        assert "synthesis" in props
        assert "ingestion" in props
        assert "distillation" in props

    def test_schema_title(self):
        schema = pipeline_settings_schema()
        assert schema.get("title") == "PipelineSettings"

    def test_schema_selection_fields(self):
        schema = pipeline_settings_schema()
        # Selection should be a $ref or inline; find its properties in $defs
        defs = schema.get("$defs", {})
        sel = defs.get("SelectionSettings", {})
        sel_props = sel.get("properties", {})
        assert "n_select" in sel_props
        assert "n_wild" in sel_props
        assert "diversity_bonus" in sel_props
        assert "quality_floor" in sel_props
        assert "min_text_length" in sel_props
        assert "intensity_scores" in sel_props
        assert "wild_card_excluded_domains" in sel_props

    def test_schema_has_defaults(self):
        schema = pipeline_settings_schema()
        defs = schema.get("$defs", {})
        sel = defs.get("SelectionSettings", {})
        sel_props = sel.get("properties", {})
        assert sel_props["n_select"]["default"] == 9
        assert sel_props["diversity_bonus"]["default"] == 1.5


# ---------- load_pipeline_settings ----------


class TestLoadPipelineSettings:
    async def test_no_overrides_returns_defaults(self):
        """With no rows in DB, load_pipeline_settings returns all defaults."""
        from unittest.mock import AsyncMock, MagicMock

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        ps = await load_pipeline_settings(mock_session)
        assert ps == PipelineSettings()
        assert ps.selection.n_select == 9
        assert ps.threads.match_threshold == 0.75

    async def test_with_overrides(self):
        """DB overrides are merged into the defaults."""
        from unittest.mock import AsyncMock, MagicMock

        class FakeRow:
            def __init__(self, key, value):
                self.key = key
                self.value = value
                self.category = "pipeline"

        rows = [
            FakeRow("pipeline.selection.n_select", 12),
            FakeRow("pipeline.synthesis.plan_retries", 5),
            FakeRow("pipeline.threads.deactivation_days", 30),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        ps = await load_pipeline_settings(mock_session)
        assert ps.selection.n_select == 12
        assert ps.synthesis.plan_retries == 5
        assert ps.threads.deactivation_days == 30
        # Unchanged defaults preserved
        assert ps.selection.n_wild == 1
        assert ps.ingestion.max_total == 80

    async def test_key_without_pipeline_prefix(self):
        """Keys without 'pipeline.' prefix are handled correctly."""
        from unittest.mock import AsyncMock, MagicMock

        class FakeRow:
            def __init__(self, key, value):
                self.key = key
                self.value = value
                self.category = "pipeline"

        rows = [FakeRow("selection.quality_floor", 0.9)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        ps = await load_pipeline_settings(mock_session)
        assert ps.selection.quality_floor == 0.9
