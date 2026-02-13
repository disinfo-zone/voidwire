"""Synthesis Pass B prompt builder."""
from __future__ import annotations
import json
from datetime import date
from typing import Any


def build_prose_prompt(
    ephemeris_data: dict,
    selected_signals: list[dict],
    thread_snapshot: list[dict],
    date_context: date,
    interpretive_plan: dict | None = None,
    sky_only: bool = False,
) -> str:
    plan_str = json.dumps(interpretive_plan, indent=2) if interpretive_plan else "(no plan)"
    titles = ephemeris_data.get("recent_titles", [])
    titles_str = ", ".join(f'"{t}"' for t in titles) if titles else "(none)"

    signals_str = ""
    if not sky_only and selected_signals:
        for s in selected_signals:
            wild = " [WILD CARD]" if s.get("was_wild_card") else ""
            signals_str += f"\n- [{s.get('id','?')}] ({s.get('domain','?')}/{s.get('intensity','?')}) {s.get('summary','')}{wild}"

    threads_str = ""
    for t in (thread_snapshot or [])[:10]:
        threads_str += f"\n- {t.get('canonical_summary','')} ({t.get('domain','')}, {t.get('appearances',0)} appearances)"

    sky_note = "\nThe cultural signal is absent today. Read only the planetary weather.\n" if sky_only else ""

    return f"""You are a cultural seismograph. Your prose uses proper em-dashes (\u2014), not hyphens or en-dashes.

TODAY: {date_context.isoformat()}

=== INTERPRETIVE PLAN ===
{plan_str}

=== TRANSIT DATA ===
{json.dumps(ephemeris_data, indent=2, default=str)}

=== CULTURAL SIGNALS ==={signals_str or " (none)"}

=== ACTIVE THREADS ==={threads_str or " (none)"}
{sky_note}
HARD CONSTRAINTS (violation = rejection):
- Do NOT address the reader as "you." Do not give advice or prescriptions.
- No emojis, ever.
- Use proper em-dashes (\u2014) for parenthetical asides, never hyphens or en-dashes.
- Standard reading body: 400\u2013600 words. Extended reading: 1200\u20131800 words.
- Title must not resemble any of: {titles_str}
- Do not use the words: "buckle up", "wild ride", "cosmic", "universe has plans", "energy", "vibe"
- Every transit annotation must reference a specific aspect from the transit data.

STRUCTURE:
Generate JSON with these fields:
- standard_reading: {{title, body, word_count}}
- extended_reading: {{title, subtitle, sections: [{{heading, body}}], word_count}}
- transit_annotations: [{{aspect, gloss, cultural_resonance, temporal_arc}}]

Return ONLY valid JSON, no markdown fencing."""
