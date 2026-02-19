# VOIDWIRE

A daily automated astrological reading system that combines real planetary transit data with cultural signal analysis through LLM synthesis. Voidwire is a cultural seismograph: it uses the astrological frame as a symbolic grammar for reading the pressure, drift, and undertow of the world on any given day.

The system calculates real planetary transits from Swiss Ephemeris data, ingests and distills news into archetypal signal vectors, then synthesizes these two streams through a two-pass LLM pipeline into prose that reads as oracular interpretation. News does not cause the reading -- it provides the language through which the planetary weather speaks.

## Architecture

```
                DAILY PIPELINE (scheduler, advisory-locked)
    +-----------+  +-----------+  +-----------+  +-----------+
    | Ephemeris |  | Ingestion |  | Distill   |  | Embedding |
    | (swisseph)|  | (RSS +    |  | (LLM      |  | (vector   |
    |           |  | trafilat.)|  |  extract)  |  |  1536d)   |
    +-----+-----+  +-----+-----+  +-----+-----+  +-----+-----+
          |              |              |              |
          v              v              v              v
    +-----------+  +-----------+  +-----------+  +-----------+
    | Selection |  | Thread    |  | Synthesis |  | Publish   |
    | (seeded   |  | Tracker   |  | (2-pass   |  | (approval |
    |  stochas.)|  | (pgvector)|  |  LLM gen) |  |  gate)    |
    +-----------+  +-----------+  +-----------+  +-----------+

  PostgreSQL 16 + pgvector    Redis 7    Minio (S3 backups)
  FastAPI (API)    Astro (public site)    React (admin panel)
  Caddy (reverse proxy)    Cloudflare Tunnel (optional edge)
```

### Packages

| Package | Path | Description |
|---------|------|-------------|
| `voidwire-shared` | `shared/` | SQLAlchemy models, database config, LLM client, encryption |
| `voidwire-ephemeris` | `ephemeris/` | Swiss Ephemeris calculator (positions, aspects, lunar data) |
| `voidwire-pipeline` | `pipeline/` | 8-stage daily pipeline orchestrator |
| `voidwire-api` | `api/` | FastAPI application (public + admin endpoints) |
| Public site | `web/` | Astro SSR site with Svelte islands |
| Admin panel | `admin/` | React SPA with Tailwind CSS |

## Prerequisites

- Python 3.12+
- Node.js 20+ (for web and admin)
- Docker and Docker Compose
- A Cloudflare Tunnel token (for production)

## Quick Start

### Local Development

```bash
# Clone and enter
git clone <repo-url> voidwire && cd voidwire

# Copy environment config
cp .env.example .env
# Edit .env: set ENCRYPTION_KEY and SECRET_KEY (see .env.example for generation commands)

# Start infrastructure
docker compose up -d voidwire-db voidwire-redis

# Create Python environment
python3.12 -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install all packages in editable mode
pip install -e shared/ -e ephemeris/ -e pipeline/ -e api/

# Run database migrations
alembic upgrade head

# Start the API
uvicorn api.main:create_app --factory --reload --port 8000

# In another terminal, run the pipeline once manually
python -m pipeline --once
```

### Docker Compose (Production)

```bash
cp .env.example .env
# Fill in all values in .env, especially:
#   ENCRYPTION_KEY, SECRET_KEY
#   POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD

docker compose up -d
```

This starts 8 services by default: PostgreSQL + pgvector, Redis, API, pipeline, public site, admin panel, Minio, and Caddy. On first run, the setup wizard guides through admin account creation, LLM configuration, and news source seeding.

Production compose behavior:
- `docker-compose.yml` is the base file (prod-safe defaults).
- Only Caddy exposes a host port in base: `4480:80`.
- All other services communicate only on Docker internal networking.

### Docker Compose (Development Overlay)

Use the dev overlay to expose service ports locally.

Set `COMPOSE_FILE` in your local `.env`:
- Linux/macOS (`bash`/`zsh`): `COMPOSE_FILE=docker-compose.yml:docker-compose.dev.yml`
- Windows (`PowerShell`/`CMD`): `COMPOSE_FILE=docker-compose.yml;docker-compose.dev.yml`

Then run:

```bash
docker compose up -d
```

With the dev overlay enabled, host ports are exposed for:
- db `5432`, redis `6379`, api `8000`, web `4321`, admin `5173`, minio `9000/9001`
- caddy `80/443` (in addition to base `4480`)

The API container runs `alembic upgrade head` on startup before serving traffic.
At API startup, the app also validates that DB revisions match Alembic heads and fails fast if the schema is behind.
Keep `SKIP_MIGRATION_CHECK=false` for normal environments; only set it to `true` for ephemeral CI/local bypass cases.

To include Cloudflare Tunnel in production:

```bash
docker compose --profile tunnel up -d
```

When accessing services through Caddy (`http://localhost` in dev overlay, `http://localhost:4480` in base-only mode), use the `/api` prefix for API routes (example: `/api/health`, `/api/admin/auth/login`). Caddy strips `/api` before proxying to `voidwire-api`.

Local URLs:
- Public site: `http://localhost/`
- Admin UI: `http://localhost/admin/` (or `http://localhost:5173/admin/`)
- API health: `http://localhost/api/health`

### Operational Environment Knobs

- `ASYNC_JOB_RETENTION_DAYS`: retention for completed/failed async user jobs before cleanup.
- `ANALYTICS_RETENTION_DAYS`: retention for analytics events before cleanup.
- `BILLING_RECONCILIATION_INTERVAL_HOURS`: cadence for scheduled billing reconciliation.
- `SKIP_MIGRATION_CHECK`: bypass API startup revision parity check (default `false`).
- `USER_JWT_EXPIRE_MINUTES`: user auth cookie/JWT lifetime.
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PUBLISHABLE_KEY`: billing integration settings.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `APPLE_CLIENT_ID`, `APPLE_TEAM_ID`, `APPLE_KEY_ID`, `APPLE_PRIVATE_KEY`: optional OAuth defaults (can be overridden in Admin > Site Settings > OAuth Sign-In).

## Services

| Service | Host Ports | Description |
|---------|------------|-------------|
| `voidwire-db` | none in base, `5432` in dev overlay | PostgreSQL 16 with pgvector and pgcrypto |
| `voidwire-redis` | none in base, `6379` in dev overlay | Session store and rate limiting |
| `voidwire-api` | none in base, `8000` in dev overlay | FastAPI (public API + admin endpoints) |
| `voidwire-web` | none in base, `4321` in dev overlay | Astro public site |
| `voidwire-admin` | none in base, `5173` in dev overlay | React admin panel |
| `voidwire-minio` | none in base, `9000/9001` in dev overlay | S3-compatible backup storage |
| `voidwire-caddy` | `4480` in base, plus `80/443` in dev overlay | Reverse proxy with TLS |
| `cloudflared` | -- | Cloudflare Tunnel (optional via `--profile tunnel`) |

## Pipeline

The pipeline scheduler runs continuously in the pipeline container and executes daily at `PIPELINE_SCHEDULE` (default `0 5 * * *`, configurable) across 8 stages:

- Schedule source precedence: Admin UI scheduler override (stored in `site_settings`) -> `.env` defaults (`PIPELINE_SCHEDULE`, `TIMEZONE`, `PIPELINE_RUN_ON_START`)
- Changes saved in Admin > Pipeline are picked up by the scheduler loop without restarting containers

1. **Ephemeris** -- Calculates planetary positions, aspects, lunar phase, void-of-course, and 5-day forward ephemeris using Swiss Ephemeris (`pyswisseph`). Resolves archetypal meanings from a curated dictionary with compositional fallback.

2. **Ingestion** -- Fetches RSS feeds from configured news sources. Optional full-text extraction via `trafilatura`. Per-source health tracking, domain caps (15/domain, 80 total), and URL deduplication.

3. **Distillation** -- LLM extracts 15-20 structured cultural signals from articles. Each signal has a summary, domain, intensity, directionality, and entity list. JSON schema validation with one repair retry.

4. **Embedding** -- Generates 1536-dimensional embeddings for all signals via the configured embedding model.

5. **Selection** -- Seeded stochastic selection (9 signals + 1 wild card). Major signals guaranteed. Remaining slots filled by weighted random (`intensity * source_weight * diversity_bonus`). Wild card maximizes cosine distance from major signal centroid. Quality floor and domain exclusions on wild card candidates.

6. **Thread Tracking** -- Matches signals to developing cultural threads using pgvector cosine similarity with domain bonus. Recency-weighted centroid update (decay=0.8). 7-day deactivation window with reactivation support.

7. **Synthesis** -- Two-pass LLM generation. Pass A: structured interpretive plan (aspect-by-aspect readings, tone notes, wild card integration). Pass B: prose generation (standard 400-600 words, extended 1200-1800 words, transit annotations). Fallback ladder: retry -> sky-only -> silence reading.

8. **Publish** -- Stores reading with approval gate. Auto-publish applies to scheduler/default runs when enabled; manual/regeneration/event-triggered runs remain pending in the queue. Editorial overlay preserves diff between generated and published versions.

Public API/site routes only return readings with `status='published'`. Publish queued manual runs from Admin > Readings.

### Reproducibility

Every pipeline run creates an immutable record containing: exact ephemeris JSON, all distilled signals, selected signals with weights, thread snapshot, full prompt payloads, content hashes (SHA-256), seeded RNG state, model configuration, and code version (git SHA). Any historical reading can be fully explained.

### Failure Modes

The pipeline never skips daily publication. The fallback ladder degrades gracefully:

- Source failures: continue with available sources
- Distillation failure: headline-only heuristic extraction
- All sources fail: sky-only reading (ephemeris only)
- Synthesis failure: retry with stricter prompt, then sky-only, then silence reading
- Thread tracking failure: use previous run's thread snapshot

## LLM Configuration

Three configurable model slots via any OpenRouter-compatible API:

| Slot | Purpose | Suggested Model Class |
|------|---------|----------------------|
| `synthesis` | Interpretive plan + prose generation | Strong reasoning model |
| `distillation` | News extraction and signal distillation | Fast, cost-effective model |
| `embedding` | Signal and thread embeddings | Any OpenAI-compatible embedding endpoint |

All API keys are encrypted at rest using Fernet symmetric encryption. Models are swappable via admin UI at any time without code changes.

## Database

PostgreSQL 16 with extensions:
- **pgvector** -- HNSW-indexed vector columns for signal and thread embeddings
- **pgcrypto** -- UUID generation via `gen_random_uuid()`

Schema includes pipeline/editorial tables plus user-account and billing tables (`users`, `user_profiles`, `subscriptions`, `discount_codes`, token tables, Stripe webhook events, and async jobs).

Migrations managed with Alembic.

## Public Site

Astro static site with Svelte islands for interactivity. Dark aesthetic with EB Garamond typography on void-black background.

- Today's reading (standard ~500 words)
- "Descend into the ephemeris" expansion (extended reading + transit visualization)
- Archive browser
- Event pages (eclipses, lunations, retrograde stations)
- RSS 2.0 and Atom 1.0 feeds
- Dynamic site branding metadata (favicon + social card) sourced from admin-configured uploads/URLs

## Admin Panel

React SPA behind Cloudflare Access (zero-trust). TOTP login with HttpOnly admin session cookies at the application layer.

- Reading queue with inline editing and diff tracking
- News source management with health indicators
- Prompt template editor with starter template seeding (synthesis + personal reading), variable library tooltips, and version history
- Archetypal dictionary CRUD
- LLM configuration panel
- Pipeline controls and run history
- Scheduler editor (UI override + `.env` fallback), run progress hints, and reading publication status per run
- Site settings, backup/restore, audit log
- Site branding upload flow in Admin > Site Settings for favicon and Twitter/OpenGraph card image assets
- SMTP settings + test-send flow for transactional emails (verification + password reset)
- Accounts & billing controls (manual pro override, discount code management, direct user create/edit/delete)
- User account flags for product controls (`is_test_user`, `is_admin_user`) editable from Admin > Accounts
- OAuth provider configuration (Google/Apple enablement + secrets)
- Shared banned-phrase controls in Pipeline Settings (applies to synthesis + personal readings)
- Personal reading runtime controls in Pipeline Settings (enable/disable, word ranges, template names, weekly aspect cap)
- Personal reading async-job monitoring (queue/running/failed/error visibility)
- Admin RBAC management (`owner`, `admin`, `support`, `readonly`)
- Operational health/SLO panel (webhook freshness, checkout failures, token cleanup backlog, override hygiene)
- Dashboard KPIs for users, subscriptions, personal-generation throughput, and pipeline output

### User Accounts API

- Auth/session: `POST /v1/user/auth/register`, `POST /v1/user/auth/login`, `POST /v1/user/auth/logout`, `POST /v1/user/auth/logout-all`, `GET /v1/user/auth/oauth/providers`
- Verification/recovery: `POST /v1/user/auth/verify-email`, `POST /v1/user/auth/resend-verification`, `POST /v1/user/auth/forgot-password`, `POST /v1/user/auth/reset-password`
- Account management/governance: `GET /v1/user/auth/me`, `PUT /v1/user/auth/me`, `PUT /v1/user/auth/me/password`, `GET /v1/user/auth/me/export`, `DELETE /v1/user/auth/me`
- Profile + natal: `GET /v1/user/profile`, `PUT /v1/user/profile/birth-data`, `PUT /v1/user/profile/house-system`, `GET /v1/user/profile/natal-chart`, `POST /v1/user/profile/natal-chart/recalculate`
- Personalized readings: `GET /v1/user/readings/personal`, `GET /v1/user/readings/personal/current`, `POST /v1/user/readings/personal/jobs`, `GET /v1/user/readings/personal/jobs`, `GET /v1/user/readings/personal/jobs/{job_id}`, `GET /v1/user/readings/personal/history`
- Subscription/billing: `GET /v1/user/subscription`, `POST /v1/user/subscription/checkout`, `POST /v1/user/subscription/portal`, `GET /v1/user/subscription/prices`, Stripe webhook: `POST /v1/stripe/webhook`

## Testing

```bash
# Run all tests
python -m pytest

# With coverage
python -m pytest --cov=shared --cov=ephemeris --cov=pipeline --cov=api
```

Test suite includes:
- Ephemeris golden-file tests against known planetary positions
- Aspect detection and orb calculation tests
- Lunar phase and void-of-course tests
- Stochastic selection determinism tests (fixed seeds)
- Pipeline orchestrator tests with mocked stages
- API endpoint tests

CI workflows:
- `.github/workflows/ci.yml`: lint (critical changed paths), pytest, and migration head check
- `.github/workflows/perf-guard.yml`: user-path latency guardrails
- `.github/workflows/release.yml`: preflight migrations/smoke checks and production confirmation gate

### Performance Benchmarks

Run concurrent user-path benchmarks (natal calculation + personalized reading generation path):

```bash
python tests/perf/benchmark_user_paths.py --requests 40 --concurrency 8
```

Guardrail thresholds used in CI (`perf-guard.yml`):
- natal chart p95 <= `400ms`
- personal reading p95 <= `400ms`
- combined p95 mean <= `300ms`

Operational runbooks:
- `docs/runbooks/backup_restore_drill.md`
- `docs/runbooks/release.md`

## Project Structure

```
voidwire/
  design_doc.md           # Technical design document (v0.4)
  docker-compose.yml      # Base/prod-safe compose (only Caddy host port)
  docker-compose.dev.yml  # Dev overlay (adds local host port mappings)
  .env.example            # Environment template
  pyproject.toml          # Python workspace root
  alembic.ini             # Database migration config
  alembic/                # Migration versions
  shared/                 # Shared Python package
    src/voidwire/
      config.py           # Pydantic settings from env
      database.py         # Async SQLAlchemy engine/sessions
      models/             # SQLAlchemy ORM models
      services/           # LLM client, encryption
      schemas/            # Pydantic validation schemas
  ephemeris/              # Ephemeris calculator
    src/ephemeris/
      calculator.py       # calculate_day() -> EphemerisOutput
      aspects.py          # Aspect detection, orb calculations
      lunar.py            # Phase, void-of-course, ingress
      meanings.py         # Archetypal dictionary lookup
      bodies.py           # Planet definitions, orb tables
  pipeline/               # Daily pipeline
    src/pipeline/
      orchestrator.py     # Advisory-locked pipeline runner
      stages/             # 8 pipeline stages
      prompts/            # LLM prompt builders
      news/               # RSS fetcher, dedup, filters
  api/                    # FastAPI application
    src/api/
      main.py             # App factory
      routers/            # Public + admin endpoints
      middleware/          # Auth, rate limiting, setup guard
  web/                    # Astro public site
  admin/                  # React admin panel
  infra/                  # Dockerfiles, Caddyfile, cloudflared
  tests/                  # Integration tests
```

## License

AGPL-3.0. See [LICENSE](LICENSE).
