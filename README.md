# VOIDWIRE

A daily automated astrological reading system that combines real planetary transit data with cultural signal analysis through LLM synthesis. Voidwire is a cultural seismograph: it uses the astrological frame as a symbolic grammar for reading the pressure, drift, and undertow of the world on any given day.

The system calculates real planetary transits from Swiss Ephemeris data, ingests and distills news into archetypal signal vectors, then synthesizes these two streams through a two-pass LLM pipeline into prose that reads as oracular interpretation. News does not cause the reading -- it provides the language through which the planetary weather speaks.

## Architecture

```
                   DAILY PIPELINE (cron, advisory-locked)
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
  Caddy (reverse proxy)    Cloudflare Tunnel (edge)
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

# In another terminal, run the pipeline manually
python -m pipeline.orchestrator
```

### Docker Compose (Production)

```bash
cp .env.example .env
# Fill in all values in .env, especially:
#   ENCRYPTION_KEY, SECRET_KEY, CLOUDFLARE_TUNNEL_TOKEN
#   POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD

docker compose up -d
```

This starts all 9 services: PostgreSQL + pgvector, Redis, API, pipeline, public site, admin panel, Minio, Caddy, and Cloudflare Tunnel. On first run, the setup wizard guides through admin account creation, LLM configuration, and news source seeding.

## Services

| Service | Port | Description |
|---------|------|-------------|
| `voidwire-db` | 5432 | PostgreSQL 16 with pgvector and pgcrypto |
| `voidwire-redis` | 6379 | Session store and rate limiting |
| `voidwire-api` | 8000 | FastAPI (public API + admin endpoints) |
| `voidwire-web` | 4321 | Astro public site |
| `voidwire-admin` | 5173 | React admin panel |
| `voidwire-minio` | 9000/9001 | S3-compatible backup storage |
| `voidwire-caddy` | 80/443 | Reverse proxy with TLS |
| `cloudflared` | -- | Cloudflare Tunnel (no open inbound ports) |

## Pipeline

The daily pipeline runs at 05:00 UTC (configurable) and executes 8 stages:

1. **Ephemeris** -- Calculates planetary positions, aspects, lunar phase, void-of-course, and 5-day forward ephemeris using Swiss Ephemeris (`pyswisseph`). Resolves archetypal meanings from a curated dictionary with compositional fallback.

2. **Ingestion** -- Fetches RSS feeds from configured news sources. Optional full-text extraction via `trafilatura`. Per-source health tracking, domain caps (15/domain, 80 total), and URL deduplication.

3. **Distillation** -- LLM extracts 15-20 structured cultural signals from articles. Each signal has a summary, domain, intensity, directionality, and entity list. JSON schema validation with one repair retry.

4. **Embedding** -- Generates 1536-dimensional embeddings for all signals via the configured embedding model.

5. **Selection** -- Seeded stochastic selection (9 signals + 1 wild card). Major signals guaranteed. Remaining slots filled by weighted random (`intensity * source_weight * diversity_bonus`). Wild card maximizes cosine distance from major signal centroid. Quality floor and domain exclusions on wild card candidates.

6. **Thread Tracking** -- Matches signals to developing cultural threads using pgvector cosine similarity with domain bonus. Recency-weighted centroid update (decay=0.8). 7-day deactivation window with reactivation support.

7. **Synthesis** -- Two-pass LLM generation. Pass A: structured interpretive plan (aspect-by-aspect readings, tone notes, wild card integration). Pass B: prose generation (standard 400-600 words, extended 1200-1800 words, transit annotations). Fallback ladder: retry -> sky-only -> silence reading.

8. **Publish** -- Stores reading with approval gate. Auto-publish mode available. Editorial overlay preserves diff between generated and published versions.

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

17 tables covering pipeline runs, readings, cultural signals, threads, news sources, prompt templates, archetypal meanings, LLM config, astronomical events, site settings, admin users, audit log, and analytics.

Migrations managed with Alembic.

## Public Site

Astro static site with Svelte islands for interactivity. Dark aesthetic with EB Garamond typography on void-black background.

- Today's reading (standard ~500 words)
- "Descend into the ephemeris" expansion (extended reading + transit visualization)
- Archive browser
- Event pages (eclipses, lunations, retrograde stations)
- RSS 2.0 and Atom 1.0 feeds

## Admin Panel

React SPA behind Cloudflare Access (zero-trust). JWT + TOTP authentication at the application layer.

- Reading queue with inline editing and diff tracking
- News source management with health indicators
- Prompt template editor with version history
- Archetypal dictionary CRUD
- LLM configuration panel
- Pipeline controls and run history
- Site settings, backup/restore, audit log

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

## Project Structure

```
voidwire/
  design_doc.md           # Technical design document (v0.4)
  docker-compose.yml      # All 9 services
  .env.example            # Environment template
  pyproject.toml          # Python workspace root
  alembic.ini             # Database migration config
  alembic/                # Migration versions
  shared/                 # Shared Python package
    src/voidwire/
      config.py           # Pydantic settings from env
      database.py         # Async SQLAlchemy engine/sessions
      models/             # 17 SQLAlchemy ORM models
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
