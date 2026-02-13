# VOIDWIRE

### Technical Design Document v0.4

---

```
    *       .    ·          .
  .    ·         *    .
        VOIDWIRE         ·
  ·         .        *
    .    *       .         .
```

---

## CHANGELOG

**v0.4 (implementation)** reflects the initial codebase implementation and reconciliation between spec and code.

Changes from v0.3:

- **Monorepo structure implemented.** Python workspace with four packages: `shared` (models, config, services), `ephemeris` (calculator), `pipeline` (orchestrator + stages), `api` (FastAPI). Web (`web/`, Astro) and admin (`admin/`, React) as TypeScript projects. All SQLAlchemy models use `mapped_column` with strict typing.
- **Ephemeris calculator uses Moshier fallback.** When Swiss Ephemeris data files (`seas_*.se1`) are unavailable, the calculator falls back to the Moshier analytical ephemeris (`FLG_MOSEPH`) which requires no external files. Sub-arcsecond precision is only available with Swiss Ephemeris files; Moshier provides arcsecond-level accuracy sufficient for astrological orbs.
- **Setup wizard consolidated.** Initial implementation provides 4 core steps (database init, admin creation, LLM config, source seeding). Steps 5-8 (site config, backup config, dictionary seeding, review) are deferred to the Settings panel post-setup. All 8 steps remain the long-term plan.
- **Monitoring/alerting deferred.** The alerting system described in Phase 6 (Section VI.3, "no reading by 05:20" alerts, source health alerts) is not yet implemented. Pipeline failures are logged but not pushed to external notification channels. Planned for a future release.
- **Toxicity/defamation check deferred.** The wild card guardrail for "lightweight toxicity/defamation check" on selected signal summaries (Section IV.B) is noted as a planned enhancement. Current guardrails: domain exclusion (anomalous/health), quality floor (intensity/weight threshold), and minimum text length.
- **Thread stage improvements.** Recency-weighted centroid update (decay=0.8), summary update threshold (0.92), and thread reactivation for deactivated threads now implemented per spec.
- **Synthesis fallback ladder implemented.** Full retry -> sky-only -> silence chain. Pass A retries with tweaked temperature. Pass B retries 3x with decreasing temperature. If full synthesis fails, falls back to sky-only mode before silence reading.
- **HNSW vector indexes.** Both `idx_signals_embedding` and `idx_threads_embedding` HNSW indexes are conditionally created when pgvector is available.

**v0.3** incorporates two additional engineering reviews and all outstanding design decisions.

Changes from v0.2:

- **LLM layer: vendor-agnostic via OpenRouter.** All model references are now generic. Two configurable model slots (synthesis + distillation) with full endpoint/model/API key configuration. No vendor lock-in.
- **Infrastructure contradiction resolved.** All references to managed Postgres, VPS, or external static hosting removed. The system is fully self-contained: local server, Docker Compose, Cloudflare Tunnel. No external dependencies beyond API endpoints and Cloudflare edge.
- **Setup wizard added (Phase 0.5).** First-run web UI handles database initialization, admin account creation, API key configuration, source seeding, and site settings. No manual env file editing required beyond the initial Docker Compose launch.
- **Regeneration modes defined.** Three explicit modes: new prose (reuse all upstream artifacts), reselect signals (new seed, reuse distillation), full rerun (everything recomputed). Each mode creates a new immutable run record with clear provenance of which artifacts were reused.
- **Archetypal dictionary: LLM-seeded with compositional fallback.** Dictionary entries generated via LLM, curated by admin. Missing entries auto-compose from planet + aspect keyword templates. No missing entry can halt the pipeline.
- **Event pages (automated).** Standalone pages for major astronomical events (eclipses, new/full moons, retrograde stations) with dedicated readings generated from event-specific prompt templates.
- **Backups: configurable S3 endpoint.** Admin UI allows setting any S3-compatible endpoint (local Minio, Backblaze B2, Wasabi, AWS S3). Offsite replication is a configuration choice, not an architecture change.
- **Artifact retention policy.** Large run artifacts (prompt payloads, full model responses) stored in Postgres with configurable retention. Pruning job preserves hashes, signal IDs, weights, and explainability summaries indefinitely; full blobs pruned after configurable window (default 90 days).
- **Schema refinements.** `mapped_transits` changed from TEXT[] to JSONB on threads table. HNSW indexes replace IVFFLAT for pgvector. Nullable embeddings handled throughout. Per-source `allow_fulltext_extract` flag. Reading uniqueness constraints. Timezone-aware `date_context` derivation.
- **Synthesis fallback ladder.** Graduated degradation: retry Pass B with stricter prompt, fall back to standard-only, fall back to Silence reading. Daily publication is never skipped.
- **Wild card quality floor.** Minimum intensity or source weight threshold. Domain exclusions. Stored distance calculations for explainability.
- **Admin analytics embed.** Configurable tracking script/pixel field in site settings for third-party analytics (Plausible, Umami, or any embed).
- **Pre-launch warm-up.** Implementation plan includes 7-10 days of pipeline operation before public launch to populate the thread tracker.

Changes from v0.1 (in v0.2):

- Reproducibility as north star (immutable run records)
- Kubernetes removed, infrastructure simplified
- SQLite eliminated, PostgreSQL + pgvector unified
- News ingestion hardened (legal, operational, fallbacks)
- Ephemeris schema tightened (coordinate system, datetimes, phase definitions)
- Stochastic selection refined (semantic distance wild card)
- Thread tracker formalized (embedding centroids, relational schema)
- Two-pass synthesis (interpretive plan then prose)
- Editorial workflow with audit logging and diff storage
- Failure modes defined (Silence reading)
- Admin behind Cloudflare Access zero-trust
- Transit visualization: SVG/D3, admin-switchable grid/wheel

---

## I. PREMISE

Voidwire is a daily automated astrological reading system that treats planetary transits as structural skeleton and ambient cultural signal as interpretive flesh. It is not a horoscope generator. It is a cultural seismograph that uses the astrological frame as a symbolic grammar for reading the pressure, drift, and undertow of the world on any given day.

The system calculates real planetary transits from ephemeris data, ingests and distills news and cultural chatter into archetypal vectors, then synthesizes these two streams through an LLM into prose that reads as oracular interpretation. The astrological weather provides deterministic structure and forward-looking narrative arc. The cultural injection provides vocabulary, texture, and grounding in the actual. The synthesis voice holds the tension between these with the sophistication of someone who takes symbolic systems seriously without insisting on literal mechanism.

The key design insight: news does not cause the reading. It provides the language through which the planetary weather speaks. A Mars-Saturn square reads differently during a banking crisis than during a territorial conflict, because the archetypal pressure finds expression through whatever is actually happening. Voidwire automates the process a skilled astrologer performs intuitively -- reading the sky through the world and the world through the sky.

### Design Principles

**Each day is a reproducible build artifact.** Every run stores its exact inputs (ephemeris, signals, seeds, prompt payloads, model versions, template versions). Any historical reading can be fully explained: why these signals were selected, what weights produced the ranking, which seed drove the stochastic choice. The system is debuggable and auditable without sacrificing the stochastic layer that makes it alive.

**Stochastic resonance over rational selection.** The system deliberately introduces structured randomness into which cultural signals reach the synthesis layer. Divinatory systems derive their power from unexpected juxtaposition. If the LLM sees everything and chooses rationally, it produces the obvious mapping every time. Controlled randomness -- specifically, semantic distance maximization for the wild card -- forces surprising connections that are orthogonal to the main narrative, not merely noisy.

**Lean memory, rich calculation.** The system does not remember its own prose. It tracks cultural threads as structured metadata with a rolling window. Each day's reading is interpreted fresh, with awareness of developing threads but without anchoring to previous output. This prevents narrative inertia while preserving continuity.

**Deterministic frame, emergent interpretation.** Transit data is calculable weeks ahead and provides the forward-looking capacity without requiring prediction of events. The system knows Mars perfects its square to Saturn in three days -- that is astronomy, not prophecy -- but it reads as directionality and arc.

**Archetypal meanings are pre-computed, not hallucinated.** The LLM does not interpret planetary aspects from scratch. A curated dictionary of archetypal core meanings is maintained in the codebase and injected into the synthesis prompt. The LLM's job is to apply the lens to the cultural material, not to invent the lens. This anchors the system to a consistent epistemological frame and prevents the model from drifting into generic astrology platitudes.

**The aesthetic is the epistemology.** Voidwire's visual and textual presentation is not decoration. The darkness, the restraint, the typographic gravity communicate the system's relationship to truth: serious engagement with symbolic systems, sophisticated ambiguity about mechanism, invitation to find meaning without instruction to believe.

---

## II. SYSTEM ARCHITECTURE

### High-Level Overview

```
+------------------------------------------------------------------+
|                         DAILY PIPELINE                           |
|                    (cron: 05:00 UTC daily)                       |
|                                                                  |
|  Pipeline acquires Postgres advisory lock keyed by date_context. |
|  If lock already held, exit (prevents duplicate generation).     |
|  All stages are idempotent within a run_id.                      |
|                                                                  |
|  date_context = current date in site_settings.timezone at        |
|  pipeline start (NOT UTC date). Timezone stored in run record.   |
|                                                                  |
|  +------------------+    +-------------------+                   |
|  |   EPHEMERIS      |    |   NEWS INGESTION  |                   |
|  |   CALCULATOR     |    |   + DISTILLATION  |                   |
|  |                  |    |                   |                   |
|  |  Swiss Ephemeris |    |  RSS feeds +      |                   |
|  |  pyswisseph      |    |  trafilatura      |                   |
|  |                  |    |  extraction        |                   |
|  |  Outputs:        |    |  -> keyword filter |                   |
|  |  - positions     |    |  -> distillation   |                   |
|  |  - aspects       |    |     (distil model) |                   |
|  |  - orbs/arc      |    |  -> stochastic     |                   |
|  |  - forward 5d    |    |     selection      |                   |
|  |  - lunar data    |    |     (seeded)       |                   |
|  |  - archetypal    |    |                   |                   |
|  |    core meanings |    |  Outputs:         |                   |
|  +--------+---------+    |  - signal vectors |                   |
|           |              |  - embeddings     |                   |
|           |              +--------+----------+                   |
|           |                       |                              |
|           v                       v                              |
|  +------------------------------------------------+             |
|  |          THREAD TRACKER (pgvector)              |             |
|  |                                                 |             |
|  |  7-day rolling window of cultural threads       |             |
|  |  Embedding centroid matching with recency decay  |             |
|  |  Relational: threads, signals, thread_signals   |             |
|  +------------------------+-----------------------+              |
|  |                                                 |             |
|  |          RUN RECORD (immutable)                 |             |
|  |                                                 |             |
|  |  Persists: ephemeris JSON, distilled signals,   |             |
|  |  selected signals + weights, thread snapshot,   |             |
|  |  final prompt payload(s), seed, template        |             |
|  |  versions, model versions, git SHA              |             |
|  +------------------------+-----------------------+              |
|                           |                                      |
|                           v                                      |
|  +------------------------------------------------+             |
|  |          SYNTHESIS ENGINE (two-pass)            |             |
|  |                                                 |             |
|  |  Pass A: Interpretive Plan                      |             |
|  |    Structured outline: aspect-by-aspect          |             |
|  |    readings, thread references, tone notes       |             |
|  |                                                 |             |
|  |  Pass B: Prose Generation                        |             |
|  |    Standard reading (~400-600 words)             |             |
|  |    Extended reading (~1200-1800 words)            |             |
|  |    Transit annotations for visualization         |             |
|  |                                                 |             |
|  |  Output validation: JSON schema check            |             |
|  |  -> repair loop (1 retry) -> fail with error     |             |
|  +------------------------+-----------------------+              |
|                           |                                      |
|                           v                                      |
|  +------------------------------------------------+             |
|  |          APPROVAL GATE                          |             |
|  |                                                 |             |
|  |  Reading stored as "generated" artifact          |             |
|  |  Admin edits stored as overlay with diff          |             |
|  |  "Published" is a separate artifact with          |             |
|  |  provenance chain back to generated               |             |
|  |  Full audit log of all actions                    |             |
|  +------------------------------------------------+             |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
|                        DATA STORES                               |
|                                                                  |
|  PostgreSQL 16 + pgvector          Redis 7                       |
|  (local container, vol mount)      (ephemeral only)              |
|  - pipeline_runs (immutable)       - session store               |
|  - readings (generated/published)  - rate limiting               |
|  - cultural_signals                - daily cache TTL             |
|  - cultural_threads                                              |
|  - thread_signals (link table)     Minio (local container)       |
|  - news_sources                    - local S3 storage            |
|  - prompt_templates (versioned)                                  |
|  - archetypal_meanings             Configurable S3 (remote)      |
|  - llm_config                      - offsite encrypted backups   |
|  - astronomical_events             - export archives             |
|  - site_settings                                                 |
|  - admin_users / audit_log                                       |
|  - analytics_events                                              |
|  - setup_state                                                   |
|                                                                  |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
|                      SERVING LAYER                               |
|                                                                  |
|  Public Site              Admin UI              API              |
|  (voidwire.disinfo.zone)  (behind Cloudflare    (FastAPI)        |
|  Astro (local container)   Access zero-trust)                    |
|  Cloudflare Tunnel ->                                            |
|  edge cache + DDoS         admin.voidwire.                       |
|                            disinfo.zone                          |
|  - Today's reading                                               |
|  - Expand to full         - Reading queue       - Pipeline       |
|  - Transit viz (SVG/D3)   - Source mgmt           trigger        |
|  - Archive browser        - Prompt editor       - Health         |
|  - RSS/Atom feed          - Analytics             checks        |
|  - Public API (/v1/)      - Site settings       - Webhooks       |
|    rate-limited            - Backup/restore                       |
|                           - Audit log viewer                     |
+------------------------------------------------------------------+
```

### Infrastructure Topology

The system runs one heavy job per day and serves mostly static content. Kubernetes is unnecessary. Everything runs on a local server behind Cloudflare Tunnels.

```
PRODUCTION ENVIRONMENT

  Local Server (Docker Compose)
  +------------------------------------------+
  |  voidwire-api      (FastAPI)             |
  |  voidwire-admin    (React SPA, Caddy)    |
  |  voidwire-pipeline (Python, cron)        |
  |  voidwire-web      (Astro SSR / static)  |
  |  voidwire-db       (PostgreSQL 16 +      |
  |                      pgvector)           |
  |  voidwire-redis    (Redis 7)             |
  |  voidwire-minio    (S3-compatible,       |
  |                      encrypted backups)  |
  |  voidwire-caddy    (reverse proxy, TLS   |
  |                      termination)        |
  |  cloudflared       (Cloudflare Tunnel)   |
  +------------------------------------------+
        |
        | Cloudflare Tunnel (encrypted, no open ports)
        v
  Cloudflare Edge
  +------------------------------------------+
  |  voidwire.disinfo.zone                   |
  |    -> voidwire-web (public site)         |
  |                                          |
  |  admin.voidwire.disinfo.zone             |
  |    -> voidwire-admin                     |
  |    -> Cloudflare Access (zero-trust)     |
  |                                          |
  |  api.voidwire.disinfo.zone               |
  |    -> voidwire-api (public + admin)      |
  |                                          |
  |  DDoS protection, edge caching,          |
  |  no origin IP exposed                    |
  +------------------------------------------+
```

Everything is self-contained on the local server. No managed services, no external hosting dependencies. PostgreSQL and Minio run as containers with volume mounts for persistence. Cloudflare Tunnel exposes the services without opening any inbound ports on the local network -- the `cloudflared` daemon maintains an outbound-only encrypted connection to Cloudflare's edge.

The admin panel is gated behind Cloudflare Access (zero-trust) at the edge layer, so the admin login form is never exposed to the open internet. Authentication still exists at the application layer (JWT + TOTP) as defense-in-depth.

The daily pipeline runs as a cron-triggered process inside the Docker environment. On publish, the API either triggers an Astro rebuild (if using SSR/static hybrid) or simply invalidates the Cloudflare cache for the reading pages. Since everything is local, the Astro site can fetch reading data directly from the API container over the Docker network at build/request time.

---

## III. DATABASE SCHEMA

PostgreSQL 16 with pgvector extension. All timestamps RFC 3339 / UTC. All JSONB columns have defined schemas validated at the application layer.

### Core Tables

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS pgvector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- PIPELINE RUNS: immutable record of every generation attempt
-- ============================================================
CREATE TABLE pipeline_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date_context    DATE NOT NULL,           -- which "day" this run generates for
    run_number      INTEGER NOT NULL DEFAULT 1, -- allows multiple runs per day (regenerate)
    started_at      TIMESTAMPTZ NOT NULL,
    ended_at        TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running','completed','failed')),

    -- Reproducibility inputs
    code_version    TEXT NOT NULL,            -- git SHA
    seed            BIGINT NOT NULL,          -- deterministic seed for stochastic selection
    template_versions JSONB NOT NULL,         -- {template_name: version_id, ...}
    model_config    JSONB NOT NULL,           -- {synthesis: {endpoint, model, key_ref},
                                              --  distillation: {endpoint, model, key_ref},
                                              --  embedding: {endpoint, model, key_ref}}
    regeneration_mode TEXT,                   -- NULL for initial run; 'prose_only', 'reselect', 'full_rerun'
    parent_run_id   UUID REFERENCES pipeline_runs(id),  -- if regeneration, points to original run
    reused_artifacts JSONB,                   -- which upstream artifacts were reused (by content hash)

    -- Persisted artifacts (exact inputs to synthesis)
    ephemeris_json      JSONB NOT NULL,
    distilled_signals   JSONB NOT NULL,       -- all signals from distillation
    selected_signals    JSONB NOT NULL,       -- subset chosen for injection + weights
    wild_card_signal_id TEXT,
    wild_card_distances JSONB,               -- centroid + per-candidate distances for explainability
    thread_snapshot     JSONB NOT NULL,       -- active threads at time of generation
    prompt_payloads     JSONB NOT NULL,       -- exact prompts sent to LLM(s) (prunable)

    -- Content hashes for artifact identity (survive pruning)
    ephemeris_hash      TEXT NOT NULL,        -- SHA-256 of ephemeris_json
    distillation_hash   TEXT NOT NULL,        -- SHA-256 of distilled_signals
    selection_hash      TEXT NOT NULL,        -- SHA-256 of selected_signals + seed

    -- Outputs
    interpretive_plan   JSONB,               -- Pass A output
    generated_output    JSONB,               -- Pass B output (readings + annotations) (prunable)
    error_detail        TEXT,                -- if status = 'failed'
    pruned_at           TIMESTAMPTZ,         -- when large artifacts were pruned (NULL = not pruned)

    UNIQUE (date_context, run_number)
);

CREATE INDEX idx_pipeline_runs_date ON pipeline_runs(date_context DESC);

-- ============================================================
-- READINGS: generated and published artifacts
-- ============================================================
CREATE TABLE readings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES pipeline_runs(id),
    date_context    DATE NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','approved','rejected','published','archived')),

    -- Generated content (immutable once created)
    generated_standard  JSONB NOT NULL,      -- {title, body, word_count}
    generated_extended  JSONB NOT NULL,      -- {title, subtitle, sections[], word_count}
    generated_annotations JSONB NOT NULL,    -- transit annotation array

    -- Published content (may differ from generated if edited)
    published_standard  JSONB,
    published_extended  JSONB,
    published_annotations JSONB,

    -- Editorial
    editorial_diff      JSONB,               -- structured diff: generated -> published
    editorial_notes     TEXT,
    published_at        TIMESTAMPTZ,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_readings_date ON readings(date_context DESC);
CREATE INDEX idx_readings_status ON readings(status);

-- At most one published reading per date
CREATE UNIQUE INDEX idx_readings_one_published
    ON readings(date_context) WHERE status = 'published';

-- ============================================================
-- CULTURAL SIGNALS: individual distilled signals
-- ============================================================
CREATE TABLE cultural_signals (
    id              TEXT PRIMARY KEY,         -- sig_YYYYMMDD_NNN
    date_context    DATE NOT NULL,
    run_id          UUID REFERENCES pipeline_runs(id),

    summary         TEXT NOT NULL,
    domain          TEXT NOT NULL
                    CHECK (domain IN ('conflict','diplomacy','economy','technology',
                                      'culture','environment','social','anomalous',
                                      'legal','health')),
    intensity       TEXT NOT NULL
                    CHECK (intensity IN ('major','moderate','minor')),
    directionality  TEXT NOT NULL
                    CHECK (directionality IN ('escalating','stable','de-escalating',
                                              'erupting','resolving')),
    entities        TEXT[] NOT NULL DEFAULT '{}',
    source_refs     TEXT[] NOT NULL DEFAULT '{}',

    embedding       vector(1536),            -- dimension matches configured embedding model
    was_selected    BOOLEAN NOT NULL DEFAULT FALSE,
    was_wild_card   BOOLEAN NOT NULL DEFAULT FALSE,
    selection_weight FLOAT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_signals_date ON cultural_signals(date_context DESC);
CREATE INDEX idx_signals_embedding ON cultural_signals
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- ============================================================
-- CULTURAL THREADS: tracked narrative arcs
-- ============================================================
CREATE TABLE cultural_threads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_summary TEXT NOT NULL,
    domain          TEXT NOT NULL,
    first_surfaced  DATE NOT NULL,
    last_seen       DATE NOT NULL,
    appearances     INTEGER NOT NULL DEFAULT 1,
    active          BOOLEAN NOT NULL DEFAULT TRUE,

    -- Embedding: running centroid with recency weighting
    centroid_embedding vector(1536),
    mapped_transits JSONB NOT NULL DEFAULT '[]',  -- [{transit, date, relevance_score}]

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_threads_active ON cultural_threads(active, last_seen DESC);
CREATE INDEX idx_threads_embedding ON cultural_threads
    USING hnsw (centroid_embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- ============================================================
-- THREAD-SIGNAL LINK TABLE: queryable associations
-- ============================================================
CREATE TABLE thread_signals (
    thread_id       UUID NOT NULL REFERENCES cultural_threads(id),
    signal_id       TEXT NOT NULL REFERENCES cultural_signals(id),
    date_seen       DATE NOT NULL,
    similarity_score FLOAT NOT NULL,
    PRIMARY KEY (thread_id, signal_id)
);

-- ============================================================
-- NEWS SOURCES: admin-configurable feed sources
-- ============================================================
CREATE TABLE news_sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    source_type     TEXT NOT NULL CHECK (source_type IN ('rss','api')),
    url             TEXT NOT NULL,
    domain          TEXT NOT NULL,
    weight          FLOAT NOT NULL DEFAULT 0.5 CHECK (weight >= 0 AND weight <= 1),
    max_articles    INTEGER NOT NULL DEFAULT 10,
    allow_fulltext_extract BOOLEAN NOT NULL DEFAULT FALSE,  -- if false, use RSS content only
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','paused','disabled')),
    config          JSONB NOT NULL DEFAULT '{}',  -- source-specific config (API keys ref, etc)
    last_fetch_at   TIMESTAMPTZ,
    last_error      TEXT,
    error_count_7d  INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- PROMPT TEMPLATES: versioned, every save creates a version
-- ============================================================
CREATE TABLE prompt_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_name   TEXT NOT NULL,            -- e.g., 'voice_persona', 'output_constraints'
    version         INTEGER NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT FALSE,
    content         TEXT NOT NULL,
    variables_used  TEXT[] NOT NULL DEFAULT '{}',  -- extracted variable names for validation
    tone_parameters JSONB,                    -- {darkness, specificity, density, forward_lean}
    author          TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (template_name, version)
);

CREATE INDEX idx_templates_active ON prompt_templates(template_name, is_active)
    WHERE is_active = TRUE;

-- ============================================================
-- ARCHETYPAL DICTIONARY: pre-computed aspect meanings
-- ============================================================
CREATE TABLE archetypal_meanings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    body1           TEXT NOT NULL,
    body2           TEXT,                     -- NULL for single-body entries (retrogrades, ingresses)
    aspect_type     TEXT,                     -- conjunction, square, etc. NULL for non-aspect entries
    event_type      TEXT NOT NULL             -- 'aspect', 'retrograde', 'ingress', 'station', 'lunar_phase'
                    CHECK (event_type IN ('aspect','retrograde','ingress','station','lunar_phase')),
    core_meaning    TEXT NOT NULL,            -- 1-3 sentences of archetypal interpretation
    keywords        TEXT[] NOT NULL DEFAULT '{}',
    domain_affinities TEXT[] NOT NULL DEFAULT '{}',  -- which cultural domains resonate
    source          TEXT NOT NULL DEFAULT 'generated'
                    CHECK (source IN ('generated','curated')),  -- track provenance
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- PLANETARY KEYWORDS: for compositional fallback
-- ============================================================
CREATE TABLE planetary_keywords (
    body            TEXT PRIMARY KEY,         -- 'mars', 'saturn', etc.
    keywords        TEXT[] NOT NULL,          -- ['force','severance','conflict','drive']
    archetype       TEXT NOT NULL,            -- 1-sentence core archetype
    domain_affinities TEXT[] NOT NULL DEFAULT '{}'
);

CREATE TABLE aspect_keywords (
    aspect_type     TEXT PRIMARY KEY,         -- 'conjunction', 'square', etc.
    keywords        TEXT[] NOT NULL,          -- ['friction','tension','obstruction']
    archetype       TEXT NOT NULL             -- 1-sentence core archetype
);

-- ============================================================
-- SITE SETTINGS: key-value with typed values
-- ============================================================
CREATE TABLE site_settings (
    key             TEXT PRIMARY KEY,
    value           JSONB NOT NULL,
    category        TEXT NOT NULL,            -- 'general', 'pipeline', 'stochastic', 'seo',
                                              -- 'display', 'backup', 'analytics', 'llm'
    description     TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Default settings include:
-- analytics.tracking_script  (TEXT)   -- embeddable script/pixel HTML for third-party analytics
-- analytics.tracking_head    (TEXT)   -- script to inject in <head>
-- backup.s3_endpoint         (TEXT)   -- S3-compatible endpoint URL
-- backup.s3_bucket           (TEXT)   -- bucket name
-- backup.s3_access_key       (TEXT)   -- encrypted at rest
-- backup.s3_secret_key       (TEXT)   -- encrypted at rest
-- backup.s3_region           (TEXT)   -- region string
-- backup.schedule            (TEXT)   -- cron expression for automated backups
-- backup.retention_days      (INT)    -- how long to keep backups
-- display.transit_viz_mode   (TEXT)   -- 'grid' | 'wheel'
-- pipeline.artifact_retention_days (INT) -- days before pruning large run artifacts (default 90)

-- ============================================================
-- LLM CONFIGURATION: endpoint + model slots
-- ============================================================
CREATE TABLE llm_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slot            TEXT NOT NULL UNIQUE
                    CHECK (slot IN ('synthesis','distillation','embedding')),
    provider_name   TEXT NOT NULL,            -- display name (e.g., 'OpenRouter', 'Google AI')
    api_endpoint    TEXT NOT NULL,            -- base URL (e.g., 'https://openrouter.ai/api/v1')
    model_id        TEXT NOT NULL,            -- model string (e.g., 'moonshotai/kimi-k2')
    api_key_encrypted TEXT NOT NULL,          -- encrypted API key
    max_tokens      INTEGER,
    temperature     FLOAT DEFAULT 0.7,
    extra_params    JSONB NOT NULL DEFAULT '{}',  -- provider-specific params
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- ASTRONOMICAL EVENTS: pre-calculated major events for event pages
-- ============================================================
CREATE TABLE astronomical_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      TEXT NOT NULL
                    CHECK (event_type IN ('new_moon','full_moon','lunar_eclipse',
                                          'solar_eclipse','retrograde_station',
                                          'direct_station','ingress_major')),
    body            TEXT,                     -- which planet (NULL for lunations/eclipses)
    sign            TEXT,
    at              TIMESTAMPTZ NOT NULL,
    significance    TEXT NOT NULL CHECK (significance IN ('major','moderate','minor')),
    ephemeris_data  JSONB,                   -- event-specific transit data

    -- Generated reading (same structure as daily readings)
    reading_status  TEXT NOT NULL DEFAULT 'pending'
                    CHECK (reading_status IN ('pending','generated','published','skipped')),
    reading_title   TEXT,
    reading_body    TEXT,
    reading_extended JSONB,
    run_id          UUID REFERENCES pipeline_runs(id),
    published_at    TIMESTAMPTZ,
    published_url   TEXT,                    -- e.g., /events/2026-02-full-moon-virgo

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_date ON astronomical_events(at DESC);
CREATE INDEX idx_events_type ON astronomical_events(event_type, at DESC);

-- ============================================================
-- SETUP STATE: tracks first-run wizard completion
-- ============================================================
CREATE TABLE setup_state (
    id              INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- singleton row
    is_complete     BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at    TIMESTAMPTZ,
    steps_completed JSONB NOT NULL DEFAULT '[]'   -- ['db_init','admin_created','llm_configured',
                                                  --  'sources_seeded','settings_configured']
);

-- ============================================================
-- ADMIN USERS
-- ============================================================
CREATE TABLE admin_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,            -- bcrypt
    totp_secret     TEXT,                     -- encrypted at rest
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);

-- ============================================================
-- AUDIT LOG: immutable record of all admin actions
-- ============================================================
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES admin_users(id),
    action          TEXT NOT NULL,            -- 'reading.approve', 'template.edit', 'source.create', etc.
    target_type     TEXT,                     -- 'reading', 'template', 'source', 'setting'
    target_id       TEXT,
    detail          JSONB,                    -- action-specific metadata, diffs, before/after
    ip_address      INET,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_time ON audit_log(created_at DESC);
CREATE INDEX idx_audit_log_action ON audit_log(action, created_at DESC);

-- ============================================================
-- ANALYTICS EVENTS: lightweight self-hosted metrics
-- ============================================================
CREATE TABLE analytics_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      TEXT NOT NULL,            -- 'page_view', 'reading_expand', 'archive_view'
    date_context    DATE,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_analytics_time ON analytics_events(created_at DESC);
CREATE INDEX idx_analytics_type ON analytics_events(event_type, created_at DESC);
```

---

## IV. COMPONENT DESIGN

### A. Ephemeris Calculator

**Library:** `pyswisseph` (Python bindings for Swiss Ephemeris). Precision to sub-arcsecond.

**Coordinate system:** Geocentric, tropical zodiac, ecliptic longitude. True node (not mean node). No topocentric correction (irrelevant without a natal chart location).

**All datetime fields:** RFC 3339 timestamps in UTC. Derived date fields (e.g., `date_context`) are `YYYY-MM-DD` but stored as DATE type, not strings.

**Lunar `phase_pct`:** Synodic progress, 0.0 = new moon, 0.5 = full moon, 1.0 = next new moon. Not illuminated fraction. This maps cleanly to astrological phase interpretation.

**Aspect orb entry calculation:** Binary search on ephemeris positions at 2-hour intervals, refined to 15-minute precision. For outer planets (Jupiter-Pluto), 6-hour intervals are sufficient given their slow motion. Stored as RFC 3339 timestamp.

**Daily Output Schema:**

```json
{
  "date_context": "2026-02-13",
  "generated_at": "2026-02-13T05:01:12Z",
  "julian_day": 2461421.5,

  "positions": {
    "sun":     { "sign": "Aquarius", "degree": 24.73, "longitude": 324.73,
                 "speed_deg_day": 1.01, "retrograde": false },
    "moon":    { "sign": "Scorpio",  "degree": 18.41, "longitude": 228.41,
                 "speed_deg_day": 13.2, "retrograde": false },
    "mercury": { "sign": "Aquarius", "degree": 12.08, "longitude": 312.08,
                 "speed_deg_day": 1.42, "retrograde": false },
    "venus":   { "sign": "Aries",    "degree": 3.55,  "longitude": 3.55,
                 "speed_deg_day": 1.21, "retrograde": false },
    "mars":    { "sign": "Cancer",   "degree": 21.88, "longitude": 111.88,
                 "speed_deg_day": 0.62, "retrograde": false },
    "jupiter": { "sign": "Cancer",   "degree": 14.21, "longitude": 104.21,
                 "speed_deg_day": 0.11, "retrograde": false },
    "saturn":  { "sign": "Pisces",   "degree": 25.33, "longitude": 355.33,
                 "speed_deg_day": 0.05, "retrograde": false },
    "uranus":  { "sign": "Taurus",   "degree": 28.91, "longitude": 58.91,
                 "speed_deg_day": 0.02, "retrograde": false },
    "neptune": { "sign": "Aries",    "degree": 1.44,  "longitude": 1.44,
                 "speed_deg_day": 0.01, "retrograde": false },
    "pluto":   { "sign": "Aquarius", "degree": 5.12,  "longitude": 305.12,
                 "speed_deg_day": 0.01, "retrograde": false },
    "north_node": { "sign": "Pisces", "degree": 26.7, "longitude": 356.7,
                    "speed_deg_day": -0.053, "retrograde": true },
    "chiron":  { "sign": "Aries",    "degree": 22.15, "longitude": 22.15,
                 "speed_deg_day": 0.04, "retrograde": false }
  },

  "lunar": {
    "phase_name": "waning_gibbous",
    "phase_pct": 0.72,
    "void_of_course": false,
    "void_of_course_starts": null,
    "next_sign_ingress": {
      "sign": "Sagittarius",
      "at": "2026-02-14T03:22:00Z"
    }
  },

  "aspects": [
    {
      "body1": "mars",
      "body2": "saturn",
      "type": "square",
      "orb_degrees": 3.45,
      "applying": true,
      "perfects_at": "2026-02-16T14:00:00Z",
      "entered_orb_at": "2026-02-10T09:30:00Z",
      "significance": "major",
      "core_meaning": "Structural friction. Force meeting immovable restriction. The will to act compressed by the architecture of limitation. Historically correlates with infrastructure stress, military standoffs, institutional rigidity under pressure.",
      "domain_affinities": ["conflict", "economy", "legal"]
    }
  ],

  "stations_and_ingresses": [
    {
      "type": "ingress",
      "body": "venus",
      "sign": "Aries",
      "at": "2026-02-11T18:45:00Z",
      "core_meaning": "Desire enters cardinal fire. The aesthetic impulse becomes assertive, impatient. New attractions, new valuations. Art that insists rather than seduces."
    }
  ],

  "forward_ephemeris": [
    {
      "at": "2026-02-14T03:22:00Z",
      "event": "Moon enters Sagittarius",
      "significance": "minor"
    },
    {
      "at": "2026-02-15T08:00:00Z",
      "event": "Venus conjunct Neptune perfects (0d00')",
      "significance": "major",
      "core_meaning": "The dissolution of boundaries in desire and value. Idealization, glamour, deception in equal measure. The beautiful lie and the transcendent vision share a degree."
    },
    {
      "at": "2026-02-16T14:00:00Z",
      "event": "Mars square Saturn perfects (0d00')",
      "significance": "major"
    },
    {
      "at": "2026-02-18T22:10:00Z",
      "event": "Sun enters Pisces",
      "significance": "moderate"
    }
  ],

  "recent_titles": ["The Widening Gyre", "A Sulfurous Compliance", "Undertow"]
}
```

Note the inclusion of `core_meaning` on aspects and events. These are resolved through a three-tier lookup:

1. **Curated override:** Check `archetypal_meanings` table for an exact `(body1, body2, aspect_type)` match. Admin-curated entries take priority.
2. **LLM-seeded entry:** If no curated override, check for an LLM-generated entry in the same table (flagged `source = 'generated'`). The archetypal dictionary is initially seeded by running an LLM generation pass across all common body/aspect combinations, producing ~330 entries. These are reviewed and curated over time via the admin UI.
3. **Compositional fallback:** If no entry exists at all, auto-compose from planet keywords + aspect keywords. Each body has a keyword set (Mars: force, severance, conflict, drive; Saturn: structure, restriction, limitation, time). Each aspect type has a keyword set (square: friction, tension, obstruction; trine: flow, ease, harmony). The fallback produces a structured string like "Mars (force/conflict) in Square (friction/tension) with Saturn (structure/restriction)" which the synthesis LLM is capable of interpreting into prose. **No missing dictionary entry can halt the pipeline.**

The compositional fallback means the system can generate readings for any aspect combination from day one, while the curated layer improves quality over time. The admin UI provides a dictionary editor where generated entries can be reviewed, edited, or replaced.

`recent_titles` is the last 3 published reading titles, injected to prevent the LLM from repeating distinctive metaphors or titling patterns.

**Testing strategy:**

- Golden-file tests: verify positions and aspects for a handful of well-documented historical dates against published ephemerides.
- Property tests: orb monotonically decreasing when applying and increasing when separating. Retrograde detection correct at known station dates. All timestamps UTC-consistent regardless of pipeline execution timezone.
- Edge cases: void-of-course moon spanning midnight. Aspects involving retrograde direction changes. Nodes (always retrograde in mean calculation, mostly in true).

---

### B. News Ingestion and Cultural Distillation

This component has the most operational risk. The design is conservative by default.

**Legal and operational constraints (non-negotiable):**

- RSS feeds provide headlines and ledes. Full-text extraction is attempted via `trafilatura` but treated as optional enrichment, not a dependency.
- No headless browser scraping. Too brittle, too resource-heavy, too legally ambiguous.
- No paywalled content. If extraction fails (paywall, anti-bot, DOM obfuscation), fall back to RSS summary gracefully.
- All source permissions are documented per-source in the `news_sources.config` JSONB field. When in doubt, use headline + lede only.
- Social media scraping (Twitter/X) is excluded from v1. If cultural chatter signal is needed, use: Reddit (via allowed API/feeds), Wikipedia Current Events portal, curated newsletter digests (with permission), or trend aggregator APIs where ToS permits.

**Phase 1: Ingestion**

```python
# Pseudocode for daily ingestion

async def ingest_sources(run_id: str, date_context: date) -> list[RawArticle]:
    sources = await db.get_active_sources()
    articles = []

    for source in sources:
        try:
            if source.type == 'rss':
                raw = await fetch_rss(source.url)
                for entry in raw[:source.max_articles]:
                    full_text = None
                    # Only attempt extraction if explicitly permitted for this source
                    if source.allow_fulltext_extract:
                        try:
                            full_text = await asyncio.wait_for(
                                try_extract(entry.link),  # trafilatura
                                timeout=5.0  # strict timeout per article
                            )
                        except asyncio.TimeoutError:
                            full_text = None  # fall back to RSS summary
                    articles.append(RawArticle(
                        source_id=source.id,
                        title=entry.title,
                        summary=entry.summary,
                        full_text=full_text,  # may be None
                        url=entry.link,
                        published_at=entry.published,
                        domain=source.domain,
                        weight=source.weight,
                    ))
            elif source.type == 'api':
                raw = await fetch_api(source)
                # adapter pattern per API type
                articles.extend(adapt_api_response(raw, source))

            await db.update_source_health(source.id, success=True)

        except Exception as e:
            await db.update_source_health(source.id, success=False, error=str(e))
            logger.warning(f"Source {source.name} failed: {e}")
            continue  # never let one source kill the pipeline

    # Deduplication: URL normalization + title embedding similarity
    articles = deduplicate(articles)

    # Hard cap: if big news day produces 200+ articles, cap per domain
    articles = apply_domain_caps(articles, max_per_domain=15, max_total=80)

    return articles
```

**Phase 2: Distillation**

The distillation model (configured in the distillation LLM slot) processes the article batch and produces structured cultural signals. A keyword/relevance filter runs before the LLM call to discard obvious noise (sports scores, celebrity gossip, listicles, weather forecasts unless extreme).

```
DISTILLATION PROMPT (editable via admin, version-controlled):

You are a cultural analyst extracting archetypal currents from today's news.

For each significant development, extract:
1. A thematic summary (1-2 sentences, emphasizing the archetypal quality
   of the event -- what kind of pressure or shift it represents, not
   just what happened)
2. Domain: conflict | diplomacy | economy | technology | culture |
   environment | social | anomalous | legal | health
3. Intensity: major (leading multiple outlets) | moderate (notable) | minor (texture)
4. Directionality: escalating | stable | de-escalating | erupting | resolving
5. Key entities (use archetypal framing where possible:
   "major power" not specific nation names, "tech conglomerate" not company names
   -- retain specifics only when the specificity is essential to meaning)

From these {N} articles, extract 15-20 significant cultural signals.
Return as JSON array. No preamble, no markdown fencing.
```

Output validated against a strict JSON schema. If validation fails: one retry with the invalid output + validation errors appended to the prompt. If still invalid: fail the distillation stage, log error, and generate a sky-only reading (see Failure Modes).

**Phase 3: Embedding and Stochastic Selection**

Each distilled signal is embedded via the configured embedding model and stored in `cultural_signals` with its embedding vector.

The stochastic selection algorithm:

```python
def select_signals(
    signals: list[Signal],
    major_news_embeddings: list[vector],
    seed: int,
    n_select: int = 9,
    n_wild: int = 1,
) -> list[Signal]:
    """
    Select signals for injection into synthesis prompt.

    1. FLOOR: All 'major' intensity signals are guaranteed inclusion.
    2. FILL: Remaining slots filled by weighted random selection.
       Weight = intensity_score * source_weight * domain_diversity_bonus
       Domain diversity bonus: 1.5x for underrepresented domains in current selection.
    3. WILD CARD: The wild card slot selects the signal with the
       highest cosine distance from the centroid of major signals,
       provided it passes a minimum quality threshold.
       This ensures the wild card is orthogonal to the main narrative,
       not merely random noise.
    4. GUARDRAILS:
       - Wild card candidates must be at least 'moderate' intensity
         OR have source_weight >= 0.5. Pure 'minor' from low-weight
         sources are excluded.
       - Signals from 'anomalous' or 'health' domains are excluded
         from wild card unless explicitly enabled in admin settings.
       - (Planned) A lightweight toxicity/defamation check on all selected
         signal summaries before injection. Not yet implemented.
       - Wild card candidates must pass minimum text length and
         language checks (no accidental 404 pages or non-English content).
       - If no candidate passes all constraints, the wild card slot
         is filled by the next-best candidate that passes constraints,
         or left empty (reading proceeds with n_select - 1 signals).

    All weights, scores, centroid vector hash, per-candidate distances,
    and selection rationale are stored in the run record
    (pipeline_runs.selected_signals and pipeline_runs.wild_card_distances).
    """
    rng = random.Random(seed)

    # ... implementation ...

    return selected
```

The seed is derived from `hash(date_context + run_id)` and stored in `pipeline_runs.seed`. On regenerate, a new seed is generated and stored with the new run record. This makes "why did it pick that signal" always answerable.

---

### C. Thread Tracker

Threads represent developing cultural narratives tracked across days. The system uses pgvector for embedding-based matching with relational tables for queryability.

**Thread matching algorithm:**

```python
async def match_and_update_threads(
    today_signals: list[Signal],
    date_context: date,
) -> list[Thread]:
    active_threads = await db.get_active_threads()

    for signal in today_signals:
        best_match = None
        best_score = 0.0

        for thread in active_threads:
            # Hybrid matching: embedding similarity + domain overlap
            sim = cosine_similarity(signal.embedding, thread.centroid_embedding)
            domain_bonus = 0.1 if signal.domain == thread.domain else 0.0
            score = sim + domain_bonus

            if score > THREAD_MATCH_THRESHOLD and score > best_score:
                best_match = thread
                best_score = score

        if best_match:
            # Update existing thread
            best_match.centroid_embedding = recency_weighted_centroid(
                best_match.centroid_embedding,
                signal.embedding,
                decay=0.8  # recent signals weighted more heavily
            )
            best_match.last_seen = date_context
            best_match.appearances += 1
            # Update canonical summary only if similarity is very high
            if best_score > SUMMARY_UPDATE_THRESHOLD:
                best_match.canonical_summary = signal.summary
            await db.link_thread_signal(best_match.id, signal.id, date_context, best_score)
        else:
            # Create new thread
            new_thread = Thread(
                canonical_summary=signal.summary,
                domain=signal.domain,
                first_surfaced=date_context,
                last_seen=date_context,
                centroid_embedding=signal.embedding,
            )
            await db.create_thread(new_thread)
            await db.link_thread_signal(new_thread.id, signal.id, date_context, 1.0)

    # Deactivate threads not seen in 7 days
    await db.deactivate_stale_threads(cutoff=date_context - timedelta(days=7))

    return await db.get_active_threads()
```

**Thread identity rules:**

- A thread's `canonical_summary` is its stable identity. It only updates when a new signal matches with very high confidence (above `SUMMARY_UPDATE_THRESHOLD`, e.g. 0.92). Otherwise, the signal is linked to the thread but the thread's description stays stable.
- Two threads in the same domain with centroid similarity above 0.90 are candidates for merging. Merging requires manual confirmation in the admin UI (flagged, not automatic) to prevent incorrect conflation of adjacent-but-distinct stories.
- A thread that reappears after deactivation (signal matches a deactivated thread above threshold) is reactivated, not duplicated. The `first_surfaced` date is preserved.

---

### D. Synthesis Engine

Two-pass generation with strict output validation.

**Model selection:**

**Model selection:**

Two configurable LLM slots via OpenRouter-compatible API endpoints. Fully vendor-agnostic.

- **Distillation slot:** Lower-cost model for news extraction, signal distillation, and sentiment analysis. Default: a fast, cheap model (Google Flash Lite class). Configured via admin UI or setup wizard.
- **Synthesis slot:** Higher-capability model for Pass A (interpretive plan) and Pass B (prose). This is where the reading voice lives; model quality matters. Default: a strong reasoning model (Kimi 2.5 class).
- **Embedding slot:** Any OpenAI-compatible embedding endpoint for signal and thread embeddings.

All endpoints, model IDs, API keys, and parameters stored in `llm_config` table. Recorded per-run in `pipeline_runs.model_config`. Swappable via admin UI at any time. The system makes standard OpenAI-compatible chat completion calls.

**Pass A: Interpretive Plan**

Before generating prose, the synthesis model produces a structured interpretive outline. This serves as an intermediate artifact that is easier to evaluate, edit, and critique than raw prose.

```
PASS A PROMPT (assembled from templates):

[Voice/Persona template]
[Transit data -- full ephemeris JSON]
[Cultural signals -- selected subset with framing instruction]
[Thread context -- active threads]
[Forward ephemeris]

Given the above, produce an INTERPRETIVE PLAN for today's reading.
For each major transit/aspect, specify:
- Which cultural signals it draws from (by signal ID)
- Which threads it references
- The core interpretive arc (2-3 sentences)
- Tone notes (where on the darkness/specificity/density spectrum)

For the overall reading:
- Proposed title
- Opening strategy (which image or transit leads)
- Closing strategy (which forward-looking element anchors the ending)
- Wild card integration plan (how the oblique signal enters the reading)

Return as JSON. No preamble, no markdown.
```

**Pass B: Prose Generation**

Takes the approved interpretive plan (or the raw plan if auto-publishing) and generates the actual readings.

```
PASS B PROMPT:

[Voice/Persona template -- full version]
[Interpretive plan from Pass A]
[Transit data -- for reference]
[Cultural signals -- for reference]
[Output constraints template -- word counts, structure rules, tone parameters]

HARD CONSTRAINTS:
- The reading title must not duplicate or closely resemble any of these
  recent titles: {{recent_titles}}
- No emojis. Astrological glyphs and Unicode symbols are permitted.
- Do not address the reader as "you."
- Do not give advice.
- Do not say "this is a good day for" anything.

Generate:
1. standard_reading: {title, body} (~400-600 words, single flowing narrative)
2. extended_reading: {title, subtitle, sections[]} (~1200-1800 words)
3. transit_annotations: [{aspect, gloss, cultural_resonance, temporal_arc}]

Return as JSON. No preamble, no markdown.
```

**Output validation and repair:**

```python
async def generate_with_validation(prompt: str, schema: dict, model: str) -> dict:
    """
    1. Call LLM, attempt JSON parse.
    2. Validate against schema.
    3. If invalid: re-call with original output + validation errors
       + "Return corrected JSON only."
    4. If still invalid: raise SynthesisError with readable detail.
    """
    response = await call_llm(prompt, model)

    # Strip markdown fencing if present
    text = strip_json_fencing(response)

    try:
        data = json.loads(text)
        validate(data, schema)
        return data
    except (json.JSONDecodeError, ValidationError) as e:
        # One retry with error context
        repair_prompt = f"""The following output was invalid:
{text}

Validation errors:
{str(e)}

Return ONLY the corrected JSON, with no other text."""

        response2 = await call_llm(repair_prompt, model)
        text2 = strip_json_fencing(response2)
        data2 = json.loads(text2)  # if this fails, let it raise
        validate(data2, schema)
        return data2
```

---

### E. Approval Gate and Publishing

Readings enter the queue with status `pending`. The generated content is immutable. Edits are stored as an overlay.

**Status transitions:**

```
pending -> approved -> published
pending -> rejected -> archived
pending -> [regenerate] -> new run_id, new pending reading

published -> archived (manual, e.g., to unpublish)
```

**Regeneration modes:**

When an admin triggers regeneration, the system creates a new `pipeline_run` with `parent_run_id` pointing to the original and `regeneration_mode` indicating what changed:

- **`prose_only`:** Reuses all upstream artifacts (ephemeris, distilled signals, selected signals, thread snapshot). Generates new interpretive plan and prose with a fresh LLM call. Same seed, same inputs, new output. Use when the prose quality is unsatisfactory but the signal selection is good.
- **`reselect`:** Reuses ephemeris and distilled signals. Generates a new seed, producing a different stochastic selection (different signals injected, possibly different wild card). Then runs synthesis on the new selection. Use when the signal mix feels wrong.
- **`full_rerun`:** Recomputes everything from scratch: fresh ephemeris (should be identical for the same date), fresh news ingestion, fresh distillation, new seed, new selection, new synthesis. Use for major pipeline changes or debugging.

Each mode stores `reused_artifacts` in the run record as a JSONB map of `{artifact_name: content_hash}` for every artifact carried forward from the parent run. This makes provenance unambiguous.

**Editorial overlay:**

When an admin edits a reading, the system stores:

- The published version (which may differ from generated)
- A structured diff (`editorial_diff`) showing what changed
- Who edited, when, and optional editorial notes
- All stored in the `readings` table and mirrored in `audit_log`

**Auto-publish mode:**

If enabled in settings, readings auto-publish at a configurable time (e.g., 07:00 local) unless manually held. The admin receives a notification (email or webhook) with a preview link when the reading enters `pending` status. If the admin doesn't intervene within the hold window, it publishes automatically.

**Publish action:**

On publish:

1. Reading status -> `published`, `published_at` set
2. API triggers Astro rebuild or Cloudflare cache purge for reading pages
3. RSS feed updated
4. Sitemap pinged
5. Audit log entry created

---

### F. Failure Modes and the Silence Reading

Every pipeline stage has defined fallback behavior.

| Stage            | Failure                       | Behavior                                                                                                    |
| ---------------- | ----------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Ephemeris        | pyswisseph error              | Fatal. Cannot generate without sky data. Alert admin, abort run.                                            |
| Ingestion        | All sources fail              | Generate sky-only reading (no cultural injection). Flag in admin.                                           |
| Ingestion        | Some sources fail             | Continue with available sources. Log failures.                                                              |
| Distillation     | LLM returns invalid JSON (2x) | Fall back to headline-only heuristic extraction (title + domain classification without LLM).                |
| Distillation     | LLM API down                  | Generate sky-only reading. Alert admin.                                                                     |
| Selection        | < 3 signals available         | Include all signals, no wild card. Flag as "thin signal day."                                               |
| Thread matching  | Embedding API down            | Skip thread matching for this run. Use previous day's thread snapshot. Signals stored with NULL embeddings. |
| Synthesis Pass A | Invalid output (2x)           | Skip plan, attempt Pass B directly with expanded constraints.                                               |
| Synthesis Pass B | Invalid output (1x)           | Retry with stricter prompt (shorter, fewer degrees of freedom).                                             |
| Synthesis Pass B | Invalid output (2x)           | Generate standard reading only (skip extended + annotations).                                               |
| Synthesis Pass B | Invalid output (3x)           | Fall back to Silence reading + raw ephemeris.                                                               |
| Synthesis        | LLM API down                  | Retry at configurable interval (default: 30 min, max 3 retries). If all retries fail, Silence reading.      |
| Publish          | Cache purge / rebuild fails   | Alert admin. Reading stays `approved`, manual publish.                                                      |

The synthesis fallback ladder ensures daily publication is never skipped. The system always produces *something* -- even if it's just the raw planetary data formatted typographically.

**The Silence Reading:**

When cultural injection fails entirely (all sources down, distillation broken, LLM API unavailable for distillation but available for synthesis), the system can generate a "sky-only" reading using only ephemeris data and archetypal meanings. The prompt is adjusted:

```
The cultural signal is absent today. The terrestrial channel is silent.
Read only the planetary weather. What the sky says without the world's
vocabulary to say it in.
```

This turns infrastructure failure into a diegetic event consistent with the system's voice. The reading is flagged in admin as `sky_only: true` for transparency.

If synthesis itself is unavailable, the system publishes a static template:

> *The signal is obscured. The planetary mechanism grinds on, silent and unobserved.*

Followed by the raw ephemeris data formatted as minimal, typographically beautiful text: positions, aspects, lunar phase. This is pre-written and stored as a fallback template, not LLM-generated.

---

## V. PUBLIC SITE DESIGN

### URL Structure

```
voidwire.disinfo.zone/                              # Today's reading (standard)
voidwire.disinfo.zone/archive/                      # Chronological archive
voidwire.disinfo.zone/archive/2026-02-13            # Specific date
voidwire.disinfo.zone/events/                       # Event pages index
voidwire.disinfo.zone/events/2026-03-full-moon-virgo  # Specific event page
voidwire.disinfo.zone/feed.xml                      # RSS 2.0 feed
voidwire.disinfo.zone/feed.atom                     # Atom 1.0 feed
voidwire.disinfo.zone/about                         # Colophon

api.voidwire.disinfo.zone/v1/reading/today          # Public API: today's reading
api.voidwire.disinfo.zone/v1/reading/2026-02-13     # Public API: reading by date
api.voidwire.disinfo.zone/v1/ephemeris/today        # Public API: today's transits
api.voidwire.disinfo.zone/v1/events                 # Public API: upcoming events
api.voidwire.disinfo.zone/v1/docs                   # OpenAPI documentation
```

### Technology

Astro (static-first, selective hydration). Runs as a container on the local server, served through Cloudflare Tunnel with edge caching enabled. On publish, the API triggers a rebuild or cache invalidation. The Astro site fetches reading data directly from the API container over the Docker network.

Islands of interactivity (Astro islands with Preact or Svelte):

- Transit visualization (D3/SVG, hydrated on expand)
- Expand/collapse interaction
- Archive date picker

### Interaction Model

**Default view (standard reading):**

```
+----------------------------------------------------------+
|                                                          |
|  VOIDWIRE                          2026 . 02 . 13       |
|                                                          |
|  The Tightening Square                                   |
|                                                          |
|  Mars at 21 Cancer closes its square to Saturn           |
|  in Pisces. Three degrees of orb and tightening.         |
|  The geometry of obstruction -- force meeting             |
|  architecture, impulse against restriction ...            |
|                                                          |
|  [~500 words of flowing prose]                           |
|                                                          |
|                                                          |
|            -- descend into the ephemeris --               |
|                                                          |
|                                                          |
|  archive                                      feed       |
|                                                          |
+----------------------------------------------------------+
```

**Expanded view:**

Clicking `-- descend into the ephemeris --` smoothly reveals:

1. Extended reading (sectioned prose, ~1400 words)
2. Transit visualization (SVG)

### Transit Visualization

SVG rendered with D3 (`d3-selection`, `d3-shape`). Not Canvas, not WebGL.

**Why SVG:**

- Scales perfectly to any display density
- Text rendering is native CSS, not painful Canvas fillText
- DOM-accessible (screen readers, inspect)
- For a daily static image, lighter and sharper than Canvas
- CSS `mix-blend-mode: plus-lighter` produces the glow/light-bleed effect without shaders

**Two visualization modes, admin-switchable:**

The public site supports two transit visualization modes, toggled via an admin setting. This allows development and refinement of the full ecliptic wheel while the aspect grid serves as the stable default.

**Mode A: Aspect Grid (default for launch)**

Bodies listed on rows and columns. Aspect glyphs at intersections. Orb data encoded as opacity or line weight. Applying aspects glow faintly; separating aspects dim. Compact, readable, mobile-friendly.

**Mode B: Full Ecliptic Wheel**

Traditional chart wheel rendered in SVG. The 360-degree ecliptic as a ring with sign divisions. Planetary bodies positioned at their exact longitude. Aspect lines drawn between bodies with orb-proportional weight. Lunar phase rendered in the center. Forward ephemeris events annotated at their future positions.

The wheel is the aspirational visualization -- it carries the full weight of the illuminated manuscript aesthetic. But it requires significantly more design iteration than the grid. The admin toggle (`site_settings.transit_viz_mode = 'grid' | 'wheel'`) allows switching in production without redeployment once the wheel is ready.

Both modes share the same data interface (the `transit_annotations` output from synthesis) and the same interaction model (hover/tap to reveal annotation detail).

**Visual design (both modes):**

Color: fine lines in muted gold (#c8baa8) on void-black (#050505). Astrological glyphs rendered in EB Garamond (which includes many astronomical/astrological Unicode glyphs) or a dedicated astro symbol font.

Hover/tap on an aspect cell (grid) or aspect line (wheel) reveals the transit annotation (gloss, cultural resonance, temporal arc) in a tooltip or slide panel.

### Aesthetic Specification

```css
:root {
  --void:           #050505;
  --surface:        #0a0a09;
  --text-primary:   #c0b0a0;
  --text-secondary: #9a8a7a;
  --text-muted:     #555550;
  --text-ghost:     #302e2a;
  --accent:         #c8baa8;
  --accent-glow:    rgba(180, 160, 140, 0.3);

  --font-body:      'EB Garamond', Georgia, serif;
  --font-system:    monospace;
  --font-size-body: 1.1rem;
  --line-height:    1.75;

  --max-width:      720px;
  --padding-x:      2rem;
}
```

Background: subtle ambient animation consistent with disinfo.zone's void canvas. A lightweight canvas element behind the content layer -- particle drift or Perlin noise field. Performance-budgeted: < 5% GPU on mobile, no scroll jank, requestAnimationFrame with visibility-based throttling.

Typography is primary. The reading text must feel typeset. Proper em-dashes (`&mdash;`), typographic quotes (`&ldquo;` `&rdquo;`), small caps for astrological abbreviations where appropriate. No bold in reading prose. Italic for emphasis and astrological notation.

---

## VI. ADMIN UI DESIGN

The admin panel is behind Cloudflare Access (zero-trust, configured at the tunnel level). No public-facing login form. The admin UI itself is a React SPA served from a local container.

### Sections

**1. Reading Queue** -- Primary workspace. Shows today's pending reading with full context: transit data, injected signals, thread context, both readings (standard + extended), transit annotations. Inline editing with diff tracking. Actions: approve, edit, regenerate, reject. View raw prompt payloads. Compare against previous day's reading (backed by stored run records). Signal toggle: manually include/exclude signals and regenerate. Wild card override.

**2. Source Management** -- CRUD for news sources. Name, type (rss/api), URL, domain, weight, max articles, status. Health indicators: last fetch time, error rate (7d), signals generated. Bulk operations (pause all, test fetch).

**3. Prompt Editor** -- Template editing with syntax highlighting for variable interpolation (`{{date_context}}`, `{{lunar_phase}}`, etc.). Version history with diff view. Variable validation: if a template references a variable not in the known set, warn on save. Tone control sliders (darkness, specificity, density, forward lean) mapped to numerical parameters in the output constraints template. "Test Generate" button: runs full synthesis with current templates against today's data, outputs preview without entering queue. Critical for voice iteration.

**4. Archetypal Dictionary** -- CRUD for the aspect/event meaning entries. Browse by body pair, aspect type, or event type. Edit core meanings, keywords, domain affinities. These are the interpretive anchors the LLM works from.

**5. Analytics** -- Visitor metrics via configurable tracking embed (Plausible, Umami, or any third-party script -- admin pastes the embed code in Settings). Pipeline health: success/fail rates, generation times, source health, signal counts. Content metrics: reading lengths, most-referenced transits, domain distribution, wild card integration rate, expand rate (how often visitors open the extended reading). All backed by `analytics_events` table + external analytics tool.

**6. Settings** -- General (site title, tagline, URL, timezone). Pipeline (generation time, auto-publish toggle, hold window, retry config, artifact retention days). LLM (synthesis and distillation model slots: endpoint URL, model ID, API key, temperature, max tokens -- full configuration per slot). Stochastic (signals to distill range, signals to inject range, wild card slots, major signal floor, diversity bonus multiplier, wild card domain exclusions). Display (transit visualization mode: grid or wheel). SEO (meta description, OG image, OG title template, structured data toggle, sitemap, robots.txt, canonical URL policy). Analytics (tracking script embed for `<head>`, tracking script embed for `<body>`). Backup (S3-compatible endpoint URL, bucket, access key, secret key, region, schedule, retention).

**7. Backup/Restore** -- Manual and scheduled backups to any S3-compatible endpoint (configured via Settings: local Minio, Backblaze B2, Wasabi, AWS S3, etc.). Backups encrypted before storage. Restore with selective granularity (full, readings-only, config-only). Backup includes: all Postgres data, prompt templates, site settings. Restore is tested and documented; the UI only exposes it because it's been proven to work.

**8. Audit Log** -- Chronological feed of all admin actions: template edits, source changes, reading approvals, regenerations, setting changes. Each entry shows who, when, what, and the detail/diff. Filterable by action type, target, user, date range.

---

## VII. IMPLEMENTATION PLAN

### Phase 0: Foundation (Week 1)

```
[0.1] Repository setup
      Monorepo: /api, /pipeline, /web, /admin, /ephemeris, /infra
      Python (3.12+) for api/pipeline/ephemeris
      TypeScript for web/admin

[0.2] Docker Compose for local development and production
      All services defined: api, pipeline, admin, web, db (postgres+pgvector),
      redis, minio, caddy, cloudflared
      Volume mounts for Postgres and Minio persistence
      .env.example with minimal required vars (only what can't be set via wizard)

[0.3] PostgreSQL schema
      All tables from Section III
      Migration system: Alembic
      pgvector + pgcrypto extensions enabled
      Seed script for default site_settings

[0.4] FastAPI skeleton
      Auth middleware (JWT + TOTP)
      Public endpoints (reading, archive, feed, public API v1)
      Admin endpoints (CRUD for all entities)
      Health check endpoint

[0.5] Redis configuration
      Session store, rate limiting
      No workflow state in Redis

[0.6] CI/CD skeleton
      Linting, type checking, test runner
      Docker build pipeline
```

### Phase 0.5: Setup Wizard (Week 1-2)

**Goal:** A first-run web UI that eliminates manual configuration. On fresh deployment, the system detects an incomplete setup state and redirects all requests to the wizard.

```
[0.5.1] Setup state detection
        Check setup_state table (singleton row)
        If is_complete = false, serve wizard UI on all routes
        Wizard accessible without auth (it creates the first admin)

[0.5.2] Wizard steps (sequential, resumable):

        Step 1: Database Initialization
        - Run Alembic migrations automatically
        - Seed default settings
        - Visual confirmation of table creation
        - Status: automatic, user sees progress

        Step 2: Admin Account Creation
        - Email, password (strength requirements)
        - TOTP setup with QR code
        - Creates first admin_users row

        Step 3: LLM Configuration
        - Synthesis model slot: endpoint URL, model ID, API key, test button
        - Distillation model slot: endpoint URL, model ID, API key, test button
        - Embedding model slot: endpoint URL, model ID, API key, test button
        - "Test Connection" button per slot that makes a minimal API call
          and confirms the model responds
        - Pre-filled suggestions for OpenRouter endpoints

        Step 4: News Source Seeding
        - Present default source list (AP, Reuters, Al Jazeera, etc.)
        - Checkboxes to enable/disable, weight sliders
        - Option to add custom sources
        - "Test Fetch" button per source

        Step 5: Site Configuration
        - Site title, tagline, timezone
        - Pipeline schedule (default 05:00 UTC)
        - Auto-publish toggle
        - SEO basics (meta description, OG image upload)
        - Analytics tracking embed (optional)

        Step 6: Backup Configuration (optional, skippable)
        - S3-compatible endpoint, bucket, credentials
        - "Test Connection" button
        - Backup schedule

        Step 7: Archetypal Dictionary Seeding
        - Option to generate initial dictionary via LLM
        - Uses configured synthesis model to produce ~330 entries
        - Progress bar, estimated time
        - Option to skip and use compositional fallback only

        Step 8: Review and Launch
        - Summary of all configuration
        - "Complete Setup" button
        - Marks setup_state.is_complete = true
        - Redirects to admin dashboard

[0.5.3] Post-setup behavior
        Wizard is no longer accessible after completion
        All settings editable via normal admin Settings panel
        Setup can be "reset" only via direct database intervention
        (intentionally no UI for this -- prevents accidental resets)
```

### Phase 1: Ephemeris Engine (Week 2)

```
[1.1] pyswisseph installation + Swiss Ephemeris data files

[1.2] Position calculator
      All bodies, tropical/geocentric, true node
      Speed and retrograde detection

[1.3] Aspect calculator
      Configurable orbs, applying/separating
      Perfection date calculation
      Orb entry time via binary search

[1.4] Lunar module
      Synodic phase percentage, named phases
      Void of course detection, next ingress

[1.5] Forward ephemeris (5-day lookahead)

[1.6] Archetypal meaning lookup
      Static dictionary or database-backed
      Integrated into ephemeris output

[1.7] Test suite
      Golden-file tests, property tests, edge cases

[1.8] Output schema validation
```

### Phase 2: News Pipeline (Week 3)

```
[2.1] RSS feed poller (feedparser + trafilatura)
      Headline+lede primary, full text optional
      Graceful fallback on extraction failure
      Per-source health tracking

[2.2] API source adapters
      USGS earthquake, NOAA weather
      Wikipedia Current Events (structured)
      Extensible adapter interface

[2.3] Pre-LLM keyword/relevance filter
      Discard noise before distillation
      Domain-specific discard rules (configurable)

[2.4] Distillation LLM call
      Uses configured distillation model slot
      Strict JSON schema validation + repair loop
      Domain cap enforcement

[2.5] Embedding generation
      Uses configured embedding model slot
      Stored in cultural_signals.embedding (pgvector)

[2.6] Stochastic subset selector
      Weighted selection with seed
      Semantic distance wild card
      Credibility and toxicity guardrails
      Full weight/rationale logging

[2.7] Thread tracker
      pgvector centroid matching
      Recency-weighted centroid updates
      Merge candidate flagging (admin review)
      7-day deactivation

[2.8] Deduplication pipeline
      URL normalization + title embedding clustering
```

### Phase 3: Synthesis Engine (Week 4)

```
[3.1] Prompt template system
      Database-backed, version-controlled
      Variable interpolation with validation
      Tone parameter injection

[3.2] Prompt assembler
      Modular assembly from templates + data
      Context window budget tracking
      Full payload stored in run record

[3.3] Pass A: Interpretive plan generation
      Structured output, schema-validated

[3.4] Pass B: Prose generation
      Standard + extended readings
      Transit annotations
      Recent title injection

[3.5] Output validation + repair loop

[3.6] Pipeline orchestrator
      Full pipeline: lock -> date_context (timezone-aware) ->
      ephemeris -> ingest -> distill -> select -> threads -> synthesize
      -> store -> unlock
      Idempotent per run_id
      Run record creation with content hashes
      Error handling at every stage with fallback ladder
      Cron configuration

[3.7] Regeneration modes
      prose_only: reuse all upstream, new LLM call
      reselect: new seed, reuse distillation
      full_rerun: everything from scratch
      Parent run linking and reused_artifacts tracking

[3.8] Sky-only fallback path
      Silence reading template
      Degraded generation without cultural data

[3.9] Default prompt templates + archetypal dictionary seeding
      LLM generation pass for initial ~330 dictionary entries
      Compositional fallback for missing entries

[3.10] Artifact retention / pruning job
       Configurable retention window (default 90 days)
       Prunes prompt_payloads and generated_output from old runs
       Preserves hashes, signal IDs, weights, status indefinitely

[3.11] Event page pipeline
       Pre-calculate astronomical events (eclipses, new/full moons,
       retrograde stations, major ingresses) for next 12 months
       Store in astronomical_events table
       Generate event-specific readings using event prompt templates
       (runs on configurable schedule, e.g., 3 days before event)
       Event pages published at /events/{slug}
```

### Phase 4: Admin UI (Weeks 5-6)

```
[4.1] Cloudflare Access setup for admin subdomain
      Access policies, identity provider config

[4.2] Auth system (login, TOTP, sessions)

[4.3] Reading queue
      Full context display
      Inline editing with diff tracking
      Approve / regenerate / reject
      Signal toggle, wild card override
      Raw prompt viewer
      Previous day comparison

[4.4] Source management CRUD + health display

[4.5] Prompt editor
      Syntax highlighting, version history, diff view
      Tone sliders, variable validation
      Test Generate

[4.6] Archetypal dictionary editor
      Browse, search, edit entries
      Flag LLM-generated vs curated
      Bulk generate missing entries

[4.7] Event pages management
      List upcoming astronomical events
      Generate / review / publish event readings
      Event page URL management

[4.8] LLM configuration panel
      Per-slot: endpoint, model ID, API key, params
      Test Connection button per slot
      Model swap without code changes

[4.9] Analytics dashboard
      Configurable tracking embed (paste script in settings)
      Custom pipeline metrics
      Content metrics

[4.10] Settings panel (all categories including backup S3 config)

[4.11] Backup/restore UI

[4.12] Audit log viewer
```

### Phase 5: Public Site + Public API (Weeks 6-7)

```
[5.1] Astro project setup
      Local container, served via Cloudflare Tunnel
      API data fetching over Docker network
      Cache invalidation on publish

[5.2] Today's reading page
      Typography system
      Expansion interaction (Astro island)
      Extended reading display

[5.3] Transit visualization -- Aspect Grid (Mode A)
      SVG/D3 aspect grid with hover annotations
      Muted gold on void-black aesthetic
      Responsive

[5.4] Transit visualization -- Ecliptic Wheel (Mode B)
      Full SVG chart wheel with planetary positions
      Aspect lines, sign divisions, lunar phase center
      Admin toggle between grid and wheel
      (Can ship after launch, grid is default)

[5.5] Ambient background (canvas, performance-budgeted)

[5.6] Archive page + date routing

[5.7] Event pages
      Standalone pages at /events/{slug}
      (e.g., /events/2026-03-full-moon-virgo)
      Event-specific readings with relevant transit visualization
      Linked from daily readings when relevant
      Archive of past event pages

[5.8] RSS/Atom feed generation
      Standard reading text in feed items
      Link to site for extended reading and visualization
      Proper RFC 822 / RFC 3339 datetime
      Auto-discovery link tags in HTML head
      Both RSS 2.0 and Atom 1.0 endpoints

[5.8] Public API (rate-limited)
      GET /v1/reading/today     (today's published reading)
      GET /v1/reading/:date     (archived reading by date)
      GET /v1/ephemeris/today   (today's transit data)
      Rate limiting: 60 req/hr per IP (configurable)
      JSON responses, CORS configured
      OpenAPI/Swagger docs at /v1/docs

[5.9] SEO: OG tags, JSON-LD, sitemap, robots.txt

[5.10] About/colophon page

[5.11] Performance: edge-cached via Cloudflare, minimal JS, Core Web Vitals
```

### Phase 6: Integration and Hardening (Week 8-9)

```
[6.1] End-to-end testing with real data

[6.2] Error handling hardening
      All failure modes from Section IV.F tested
      Synthesis fallback ladder verified end-to-end
      Silence reading fallback verified
      NULL embedding handling throughout thread tracker

[6.3] Monitoring and alerting (deferred)
      "No reading generated by 05:20 UTC" alert
      "Publishing failed" alert
      Source health degradation alert
      Per-stage timing and success counters
      (Not yet implemented. Pipeline failures are logged.)

[6.4] Backup/restore testing
      Prove restore works before shipping the UI for it
      Test offsite S3 backup if configured

[6.5] Security review
      Secrets management (encrypted in DB, Docker secrets for bootstrap)
      Encrypted backups verified
      Cloudflare Access zero-trust verified
      Break-glass access: document SSH tunnel to admin container
      on localhost for Cloudflare/tunnel outage scenarios
      Audit log coverage check

[6.6] Documentation
      Admin user guide, source config guide
      Prompt writing guide, deployment runbook
      Archetypal dictionary editing guide
      LLM model swap guide
      Break-glass access procedure

[6.7] Pre-launch warm-up period (7-10 days)
      Run the full pipeline daily without publishing
      Builds thread tracker history so launch-day readings
      have 7 days of cultural thread context
      Review generated readings to calibrate voice and
      tune prompt templates
      Seed archetypal dictionary curation during this period

[6.8] Production deployment
      Cloudflare Tunnel configuration
      DNS records (voidwire.disinfo.zone, admin.voidwire.disinfo.zone,
        api.voidwire.disinfo.zone)
      Cloudflare Access policies for admin
      Cloudflare cache rules for public site
      Run setup wizard
      First public reading
```

---

## VIII. COST ESTIMATION

```
Monthly at daily generation cadence:

LLM API (via OpenRouter, prices vary by model):
  Distillation (Flash Lite class):  ~$0.05-0.15/day  =  ~$2-5/mo
  Synthesis Pass A (Kimi 2.5 class):~$0.10-0.30/day  =  ~$3-9/mo
  Synthesis Pass B (Kimi 2.5 class):~$0.15-0.40/day  =  ~$5-12/mo
  Embeddings:                        ~$0.01/day       =  ~$0.30/mo
  Event page readings (~4/mo):       ~$0.50-1.50/mo

Infrastructure:
  Local server:               $0 (already owned, power/internet sunk cost)
  Cloudflare Tunnel:          $0 (free tier)
  Cloudflare Access:          $0 (free for up to 50 users)
  Domain:                     already owned
  Minio (local):              $0 (runs on same server)
  Offsite backup (if configured): ~$1-7/mo (Backblaze B2 / Wasabi)

Total (estimated):            ~$12-30/mo
```

Actual costs depend entirely on which models are configured in the LLM slots. OpenRouter pricing varies significantly by model. The architecture supports swapping to cheaper or more expensive models at any time via admin UI without code changes.

Running on local hardware with Cloudflare Tunnels eliminates all hosting costs. The only recurring expense is LLM API usage and optional offsite backups.

---

## IX. OPEN QUESTIONS FOR IMPLEMENTATION

1. **Entity anonymization granularity.** The distillation prompt says "major power" not "China" -- but some cultural signals lose essential meaning without specificity. Define a clear rule: anonymize unless specificity is load-bearing, and give the distillation LLM examples of each case.

2. **Embedding dimension portability.** The schema uses `vector(1536)` which matches OpenAI-compatible embeddings. If the embedding model changes to a different dimension, the pgvector columns and indexes need migration. Consider abstracting dimension as a config value and documenting the migration path.

3. **Thread merge UX.** How should the admin interface present merge candidates? Inline in the reading queue (where threads are contextually visible) or as a dedicated thread management view?

4. **Event page automation triggers.** Which astronomical events get automatic standalone pages? Suggested defaults: new moons, full moons, solar/lunar eclipses, outer planet retrograde stations (Jupiter-Pluto), outer planet sign ingresses. Inner planet retrogrades (Mercury, Venus, Mars) could be configurable. The ephemeris module pre-calculates these and populates `astronomical_events`; the pipeline generates readings for them on a configurable schedule (e.g., 3 days before the event).

5. **RSS feed format.** Standard reading text in feed items with a link to the site for the extended reading and transit visualization. Confirm whether Atom 1.0, RSS 2.0, or both should be supported.

---

## X. FUTURE CONSIDERATIONS

Not in v1, but architecturally accommodated:

- **Historical backtesting** (admin-only) -- run the pipeline against past dates with archived news to retroactively generate readings. Useful for calibrating voice, validating output across different astrological conditions, and populating the archive with historically interesting dates. The ephemeris module already supports arbitrary dates; the main challenge is sourcing historical news for the cultural injection layer.
- **Personalized transit-to-natal readings** (deferred -- would require user accounts, natal chart storage, additional ephemeris calculations for transit-to-natal aspects, and significantly more synthesis calls)
- **Audio/TTS** of daily readings (deferred -- the prose style is well-suited to spoken delivery but not a priority)
- **Additional public API endpoints** (transit-to-natal calculations, event calendar as iCal, historical reading search)

---

```
    .    *       .    ·          .
  ·         as below
        .        *        .    ·
    .         .        *
  *       .         .         .
```
