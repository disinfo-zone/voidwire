"""Synthesis Pass A prompt builder."""
from __future__ import annotations
import json
from datetime import date
from typing import Any

def build_plan_prompt(ephemeris_data: dict, selected_signals: list[dict], thread_snapshot: list[dict], date_context: date, sky_only: bool = False) -> str:
    signals_str = ""
    if not sky_only and selected_signals:
        for s in selected_signals:
            wild = " [WILD CARD]" if s.get("was_wild_card") else ""
            signals_str += f"\n- [{s.get('id','?')}] ({s.get('domain','?')}/{s.get('intensity','?')}) {s.get('summary','')}{wild}"
    threads_str = ""
    for t in (thread_snapshot or [])[:10]:
        threads_str += f"\n- {t.get('canonical_summary','')} ({t.get('domain','')}, {t.get('appearances',0)} appearances)"
    sky_note = "\nThe cultural signal is absent today. Read only the planetary weather.\n" if sky_only else ""
    return f"""You are a cultural seismograph reading the world through astrological symbolism.

TODAY: {date_context.isoformat()}

=== TRANSIT DATA ===
{json.dumps(ephemeris_data, indent=2, default=str)}

=== CULTURAL SIGNALS ==={signals_str or " (none)"}

=== ACTIVE THREADS ==={threads_str or " (none)"}
{sky_note}
Produce an INTERPRETIVE PLAN as JSON with: title, opening_strategy, closing_strategy, wild_card_integration, aspect_readings, tone_notes.
Return ONLY valid JSON."""
