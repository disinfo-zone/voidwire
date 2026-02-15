"""Synthesis Pass A prompt builder."""

from __future__ import annotations

import json
from datetime import date


def build_plan_prompt(
    ephemeris_data: dict,
    selected_signals: list[dict],
    thread_snapshot: list[dict],
    date_context: date,
    event_context: dict | None = None,
    sky_only: bool = False,
    thread_display_limit: int = 10,
) -> str:
    signals_str = ""
    if not sky_only and selected_signals:
        for s in selected_signals:
            wild = " [WILD CARD]" if s.get("was_wild_card") else ""
            weight = f" w={s.get('selection_weight', 0):.2f}" if s.get("selection_weight") is not None else ""
            signals_str += (
                f"\n- [{s.get('id', '?')}] "
                f"({s.get('domain', '?')}/{s.get('intensity', '?')}{weight}) "
                f"{s.get('summary', '')}{wild}"
            )

    threads_str = ""
    for t in (thread_snapshot or [])[:thread_display_limit]:
        threads_str += (
            f"\n- {t.get('canonical_summary', '')} "
            f"({t.get('domain', '')}, {t.get('appearances', 0)} appearances, "
            f"since {t.get('first_surfaced', '')})"
        )

    sky_note = "\nThe cultural signal is absent today. Read only the planetary weather.\n" if sky_only else ""
    event_block = ""
    if isinstance(event_context, dict) and event_context:
        event_block = (
            "\n=== EVENT CONTEXT (PRIMARY FOCUS) ===\n"
            f"{json.dumps(event_context, indent=2, default=str)}\n"
            "\nEvent instruction: Anchor this plan around the event context above. "
            "Signals and threads are only secondary texture.\n"
        )

    return f"""You are a cultural seismograph reading the world through astrological symbolism.

TODAY: {date_context.isoformat()}

=== TRANSIT DATA ===
{json.dumps(ephemeris_data, indent=2, default=str)}

=== CULTURAL SIGNALS ==={signals_str or " (none)"}

=== ACTIVE THREADS ==={threads_str or " (none)"}
{sky_note}
{event_block}
Produce an INTERPRETIVE PLAN as JSON with these fields:
- title: Working title for the reading
- opening_strategy: How to open (which transit or signal leads)
- closing_strategy: How to close (resolution, lingering tension, etc.)
- wild_card_integration: How to weave the wild card signal (if any) into the narrative
- aspect_readings: Array of {{aspect, interpretation, cultural_link}} for each major transit
- tone_notes: Prose style guidance (register, metaphor family, rhythm)
- thread_continuity: Which active threads to reference and how
- mention_policy: {{
    explicit_allowed: boolean (default false),
    explicit_budget: integer (0 or 1),
    allowed_entities: string[] (entities that may be named directly if explicit_allowed=true),
    rationale: string
  }}

Critical instruction:
- Allusion first. Prefer symbolic framing and subtext over direct event references.
- Explicit named references are allowed only when a connection is undeniable and structurally central.
- If EVENT CONTEXT is present, the event is the primary frame. The reading should orbit that event first.

Return ONLY valid JSON, no markdown fencing."""
