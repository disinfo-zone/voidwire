export interface TemplateVariableDefinition {
  key: string;
  description: string;
  usedIn: string;
  example: string;
}

export const TEMPLATE_VARIABLE_LIBRARY: TemplateVariableDefinition[] = [
  {
    key: 'date_context',
    description: 'ISO date for the reading day.',
    usedIn: 'Synthesis plan + prose',
    example: '2026-02-14',
  },
  {
    key: 'ephemeris_data',
    description: 'Transit and planetary context payload (JSON).',
    usedIn: 'Synthesis plan + prose',
    example: '{ "major_aspects": [...] }',
  },
  {
    key: 'selected_signals',
    description: 'Signals selected for the day after ranking and wildcard logic.',
    usedIn: 'Synthesis plan + prose',
    example: '[{ "domain": "economy", "summary": "..." }]',
  },
  {
    key: 'signals',
    description: 'Legacy alias for selected_signals in older drafts.',
    usedIn: 'Template draft compatibility',
    example: '[{ "summary": "..." }]',
  },
  {
    key: 'thread_snapshot',
    description: 'Active multi-day thread summaries for continuity.',
    usedIn: 'Synthesis plan + prose',
    example: '[{ "canonical_summary": "...", "appearances": 5 }]',
  },
  {
    key: 'event_context',
    description: 'Event payload for event-linked readings (type/body/sign/date/significance).',
    usedIn: 'Event synthesis plan + prose',
    example: '{ "event_type": "lunar_eclipse", "sign": "Virgo", "days_out": 5 }',
  },
  {
    key: 'interpretive_plan',
    description: 'Pass A plan JSON consumed by Pass B prose generation.',
    usedIn: 'Synthesis prose',
    example: '{ "opening_strategy": "...", "aspect_readings": [...] }',
  },
  {
    key: 'mention_policy',
    description: 'Validated explicit-reference policy derived from Pass A.',
    usedIn: 'Synthesis prose',
    example: '{ "explicit_allowed": false, "explicit_budget": 0 }',
  },
  {
    key: 'guarded_entities',
    description: 'Entity names that should remain allusive unless explicitly allowed.',
    usedIn: 'Synthesis prose',
    example: '["Federal Reserve", "NATO"]',
  },
  {
    key: 'explicit_entity_guard',
    description: 'Legacy alias for guarded_entities in older prompt drafts.',
    usedIn: 'Template draft compatibility',
    example: '["Federal Reserve", "NATO"]',
  },
  {
    key: 'articles',
    description: 'Raw/trimmed article blocks used during distillation.',
    usedIn: 'Distillation',
    example: '[{ "title": "...", "full_text": "..." }]',
  },
  {
    key: 'content_truncation',
    description: 'Character cap used when trimming article text.',
    usedIn: 'Distillation',
    example: '500',
  },
  {
    key: 'target_signals_min',
    description: 'Lower bound of expected extracted signals.',
    usedIn: 'Distillation',
    example: '15',
  },
  {
    key: 'target_signals_max',
    description: 'Upper bound of expected extracted signals.',
    usedIn: 'Distillation',
    example: '20',
  },
  {
    key: 'sky_only',
    description: 'Flag indicating no cultural signals are available.',
    usedIn: 'Synthesis plan + prose fallback',
    example: 'true',
  },
  {
    key: 'standard_word_range',
    description: 'Target word count range for the standard reading.',
    usedIn: 'Synthesis prose',
    example: '[400, 600]',
  },
  {
    key: 'extended_word_range',
    description: 'Target word count range for the extended reading.',
    usedIn: 'Synthesis prose',
    example: '[1200, 1800]',
  },
  {
    key: 'banned_phrases',
    description: 'Disallowed phrase list for prose output.',
    usedIn: 'Synthesis prose',
    example: '["buckle up", "wild ride"]',
  },
];

export const STARTER_TEMPLATE_DRAFT = {
  template_name: 'starter_synthesis_prose',
  content: `You are a cultural seismograph reading the world through astrological symbolism.

TODAY: {{date_context}}

=== TRANSIT DATA ===
{{ephemeris_data}}

=== CULTURAL SIGNALS ===
{{selected_signals}}

=== ACTIVE THREADS ===
{{thread_snapshot}}

=== INTERPRETIVE PLAN ===
{{interpretive_plan}}

=== MENTION POLICY ===
{{mention_policy}}

=== GUARDED ENTITIES ===
{{guarded_entities}}

=== SKY-ONLY MODE ===
{{sky_only}}

HARD CONSTRAINTS:
- Return strict JSON only (no markdown fencing).
- No emojis.
- Keep tone precise, unsentimental, and allusion-first.
- Never address the reader directly as "you".
- Standard reading body target: {{standard_word_range}} words.
- Extended reading target: {{extended_word_range}} words.
- Avoid banned phrases: {{banned_phrases}}
- Respect explicit mention policy and guarded entity constraints above.

STANDARD vs EXTENDED:
- \`standard_reading\` is the front-page dispatch: one coherent title/body unit.
- \`extended_reading\` deepens the same thesis using multiple sections and sub-arguments.
- Both should reference the same core celestial pattern, but at different levels of depth.

Write JSON with:
- standard_reading: {title, body, word_count}
- extended_reading: {title, subtitle, sections: [{heading, body}], word_count}
- transit_annotations: [{aspect, gloss, cultural_resonance, temporal_arc}]
`,
  tone_parameters: {
    register: 'analytical, literary, restrained',
    style_notes: 'image-rich but concrete',
  },
  notes: 'Starter template. Duplicate and adapt to your tone and output schema.',
};

export function variableToken(key: string): string {
  return `{{${key}}}`;
}
