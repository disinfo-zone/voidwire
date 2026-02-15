"""Synthesis Pass B prompt builder."""

from __future__ import annotations

import json
from datetime import date


def build_prose_prompt(
    ephemeris_data: dict,
    selected_signals: list[dict],
    thread_snapshot: list[dict],
    date_context: date,
    event_context: dict | None = None,
    interpretive_plan: dict | None = None,
    mention_policy: dict | None = None,
    explicit_entity_guard: list[str] | None = None,
    sky_only: bool = False,
    standard_word_range: list[int] | None = None,
    extended_word_range: list[int] | None = None,
    banned_phrases: list[str] | None = None,
    thread_display_limit: int = 10,
) -> str:
    std_range = standard_word_range or [400, 600]
    ext_range = extended_word_range or [1200, 1800]
    banned = banned_phrases or [
        "buckle up",
        "wild ride",
        "cosmic",
        "universe has plans",
        "energy",
        "vibe",
    ]
    plan_str = json.dumps(interpretive_plan, indent=2) if interpretive_plan else "(no plan)"
    titles = ephemeris_data.get("recent_titles", [])
    titles_str = ", ".join(f'"{t}"' for t in titles) if titles else "(none)"
    policy = mention_policy or {}
    explicit_allowed = bool(policy.get("explicit_allowed", False))
    try:
        explicit_budget = int(policy.get("explicit_budget", 0))
    except Exception:
        explicit_budget = 0
    explicit_budget = max(0, min(explicit_budget, 1))
    allowed_entities_raw = policy.get("allowed_entities", []) if isinstance(policy, dict) else []
    allowed_entities = [str(e).strip() for e in (allowed_entities_raw or []) if str(e).strip()][:12]
    guarded_entities = [str(e).strip() for e in (explicit_entity_guard or []) if str(e).strip()][:40]
    allowed_entities_str = ", ".join(f'"{e}"' for e in allowed_entities) if allowed_entities else "(none)"
    guarded_entities_str = ", ".join(f'"{e}"' for e in guarded_entities) if guarded_entities else "(none)"
    effective_budget = explicit_budget if explicit_allowed else 0

    signals_str = ""
    if not sky_only and selected_signals:
        for s in selected_signals:
            wild = " [WILD CARD]" if s.get("was_wild_card") else ""
            signals_str += (
                f"\n- [{s.get('id', '?')}] "
                f"({s.get('domain', '?')}/{s.get('intensity', '?')}) "
                f"{s.get('summary', '')}{wild}"
            )

    threads_str = ""
    for t in (thread_snapshot or [])[:thread_display_limit]:
        threads_str += (
            f"\n- {t.get('canonical_summary', '')} ({t.get('domain', '')}, {t.get('appearances', 0)} appearances)"
        )

    sky_note = "\nThe cultural signal is absent today. Read only the planetary weather.\n" if sky_only else ""
    event_block = ""
    if isinstance(event_context, dict) and event_context:
        event_block = (
            "\n=== EVENT CONTEXT (PRIMARY FOCUS) ===\n"
            f"{json.dumps(event_context, indent=2, default=str)}\n"
            "\nEvent instruction:\n"
            "- Make this event the primary narrative anchor for both standard and extended readings.\n"
            "- Use signals/threads only as supporting color, never as the central frame.\n"
        )

    return f"""You are a cultural seismograph. Your prose uses proper em-dashes (\u2014), not hyphens or en-dashes.

TODAY: {date_context.isoformat()}

=== INTERPRETIVE PLAN ===
{plan_str}

=== TRANSIT DATA ===
{json.dumps(ephemeris_data, indent=2, default=str)}

=== CULTURAL SIGNALS ==={signals_str or " (none)"}

=== ACTIVE THREADS ==={threads_str or " (none)"}
{sky_note}
{event_block}
HARD CONSTRAINTS (violation = rejection):
- Do NOT address the reader as "you." Do not give advice or prescriptions.
- No emojis, ever.
- Use proper em-dashes (\u2014) for parenthetical asides, never hyphens or en-dashes.
- Use cultural signals as subtext and allusion, not direct commentary.
- Do not use reportorial framing ("according to", "reported that", "headlines say", "news says").
- Standard reading body: {std_range[0]}\u2013{std_range[1]} words.
- Extended reading body: {ext_range[0]}\u2013{ext_range[1]} words.
- Title must not resemble any of: {titles_str}
- Do not use the words: {", ".join(f'"{p}"' for p in banned)}
- Every transit annotation must reference a specific aspect from the transit data.
- If EVENT CONTEXT is present, keep it as the dominant frame throughout the reading.
- Explicit mention policy:
  - Max explicit named references allowed across ALL output text: {effective_budget}
  - Explicit references may only use these entities: {allowed_entities_str}
  - Treat these entities as guarded and avoid direct naming unless allowed: {guarded_entities_str}

STRUCTURE:
Generate JSON with these fields:
- standard_reading: {{title, body, word_count}}
- extended_reading: {{title, subtitle, sections: [{{heading, body}}], word_count}}
- transit_annotations: [{{aspect, gloss, cultural_resonance, temporal_arc}}]

Return ONLY valid JSON, no markdown fencing."""
