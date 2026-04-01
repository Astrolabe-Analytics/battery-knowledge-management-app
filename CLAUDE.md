# Battery Knowledge Management App — Agent Instructions

## What This Is

Internal research library for Astrolabe's battery research team. Manages ~2,000 battery research PDFs with AI-powered RAG search, automatic metadata enrichment from CrossRef and Semantic Scholar, and a full paper management UI.

**Stack:** FastAPI + Uvicorn (Python 3.13), React 19 + Vite, PostgreSQL 16 + pgvector 0.8.0, sentence-transformers (CPU embeddings), Claude/Anthropic (RAG), AWS S3 or local filesystem (PDFs).

This project follows the agent-first operating model (see global `CLAUDE.md`). Agents plan, build, test, debug, and maintain everything.

**Start every session:** Read `tasks/lessons.md` if it exists — accumulated corrections from past sessions.

---

## Docker First

```bash
# Check state
docker ps --format "{{.Names}}\t{{.Status}}" | grep -E "api|postgres|frontend"

# Start
docker compose up -d

# Follow logs
docker compose logs -f api

# Restart after Python changes (lib/ or api/)
docker compose restart api
```

- **API (FastAPI):** http://localhost:8003
- **Frontend (Vite HMR):** http://localhost:5173
- **PostgreSQL:** localhost:5432 — user: postgres / pass: postgres / db: astrolabe

## First-Time Setup

```bash
cp .env.example .env          # then add ANTHROPIC_API_KEY
docker compose up -d          # database tables auto-created by SQLAlchemy on first startup
# Verify DB:
docker compose exec api python -c "from lib.db import check_connection; print(check_connection())"
```

## Local S3 Testing (Optional)

Default is local filesystem (`PAPERS_STORAGE` unset). To test the S3 code path:

```bash
docker compose --profile s3 up -d
./scripts/setup_localstack.sh
# Add to .env: PAPERS_STORAGE=s3 and AWS_ENDPOINT=http://localhost:4566
docker compose restart api
```

---

## Directory Map

| Path | What |
|------|------|
| `api/main.py` | FastAPI entry point — mounts 7 route modules |
| `api/routes/` | papers, search, imports, collections, history, settings, discover |
| `lib/db.py` | SQLAlchemy engine + session factory |
| `lib/db_operations.py` | All data access functions (read this before writing DB code) |
| `lib/models.py` | SQLAlchemy ORM models (Paper, Chunk, Collection, QueryHistory) |
| `lib/s3_storage.py` | PDF storage abstraction — **always use this, never raw Path("papers")** |
| `lib/llm.py` | Claude/Anthropic RAG functions |
| `lib/crossref.py` | CrossRef + Semantic Scholar metadata enrichment |
| `frontend/src/services/api.js` | All frontend API calls (centralized) |
| `scripts/ingest_pipeline_pg.py` | 4-stage ingestion pipeline (parse → chunk → metadata → embed) |
| `scripts/migrate_pdfs_to_s3.py` | Migrate local papers/ to S3 |
| `deployment/nginx.conf` | Archived legacy config (not used by current single-container deployment) |
| `deployment/ecs-task-definition.json` | ECS task definition template |
| `docs/` | Architecture docs, deployment plan |

---

## PDF Storage Modes

| Mode | `PAPERS_STORAGE` | Storage |
|------|-----------------|---------|
| **local** (default) | unset | `papers/` directory |
| **s3** | `s3` | AWS S3 or LocalStack |

**CRITICAL:** Use `lib/s3_storage.py` for ALL PDF operations:
- `pdf_exists(filename)` — check existence
- `save_pdf(filename, content)` — save on import (local + S3 in s3 mode)
- `get_presigned_url(filename)` — S3 presigned GET URL
- Never write `Path("papers") / filename` in route handlers.

---

## Ingestion Pipeline

4 stages, run sequentially:

```bash
docker compose exec api python scripts/ingest_pipeline_pg.py --stage parse --new-only
docker compose exec api python scripts/ingest_pipeline_pg.py --stage chunk --new-only
docker compose exec api python scripts/ingest_pipeline_pg.py --stage metadata --new-only
docker compose exec api python scripts/ingest_pipeline_pg.py --stage embed
```

Or trigger via the React UI import flow (calls the API which runs all stages).

---

## Tech Stack Constraints

- Python: async/await in FastAPI routes; sync SQLAlchemy in lib/ — no mixing
- All DB reads/writes via `lib/db_operations.py` only
- Parameterized SQLAlchemy queries everywhere (prevent injection)
- Frontend: React 19, Vite 7, no class components, no styled-components
- All frontend API calls go through `frontend/src/services/api.js`

---

## Production Deployment

Target: ECS Fargate, shared ALB at `knowledge.astrolabe-analytics.com`.
Single Docker image target: `api` (frontend is built into the API image and served by FastAPI static mounting).

See `docs/deployment/KNOWLEDGE_MGMT_APP_DEPLOYMENT_PLAN.md` (in data-viz-tool repo) for the full deployment plan and Hardik handoff.

```bash
# Build image
docker build --target api   -t knowledge-app-api:latest .
```

---

## Visual QA (Playwright)

Frontend E2E tests run from `frontend/`. See `.claude/rules/playwright.md` for full rules.

```bash
cd frontend
npm run test:e2e:smoke      # fast smoke check (~4s)
npm run test:e2e            # full suite with visual comparison
npm run test:e2e:update     # regenerate baselines after UI changes
```

Port 5173. If you see a title mismatch: `lsof -ti:5173 | xargs kill -9`

---

## Git Workflow

Feature branch → staging → main. Never commit directly to main.
Same workflow as data-viz-tool (see its `docs/deployment/STAGING_WORKFLOW.md`).
