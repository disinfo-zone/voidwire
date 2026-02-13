"""Synthesis Pass B prompt builder."""
from __future__ import annotations
import json
from datetime import date
from typing import Any

def build_prose_prompt(ephemeris_data: dict, selected_signals: list[dict], thread_snapshot: list[dict], date_context: date, interpretive_plan: dict | None = None, sky_only: bool = False) -> str:
    plan_str = json.dumps(interpretive_plan, indent=2) if interpretive_plan else "(no plan)"
    titles = ephemeris_data.get("recent_titles", [])
    titles_str = ", ".join(f'"{t}"' for t in titles) if titles else "(none)"
    signals_str = ""
    if not sky_only and selected_signals:
        for s in selected_signals:
            signals_str += f"\n- [{s.get('id','?')}] {s.get('summary','')}"
    return f"""You are a cultural seismograph. Your prose uses proper em-dashes, no emojis.
Do not address the reader as "you." Do not give advice.

TODAY: {date_context.isoformat()}

=== PLAN ===
{plan_str}

=== TRANSIT DATA ===
{json.dumps(ephemeris_data, indent=2, default=str)}

=== SIGNALS ==={signals_str or " (none)"}

CONSTRAINTS:
- Title must not resemble: {titles_str}
- No emojis. No "you." No advice.

Generate JSON with: standard_reading (title, body, word_count), extended_reading (title, subtitle, sections[], word_count), transit_annotations (aspect, gloss, cultural_resonance, temporal_arc).
Return ONLY valid JSON."""
