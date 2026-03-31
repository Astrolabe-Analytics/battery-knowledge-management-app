# Battery Knowledge Management App — Copilot Addenda

Full project instructions are in `CLAUDE.md`. This file adds Copilot-specific notes.

## Quick Reference

- Docker first: `docker compose up -d` → API at :8003, Frontend at :5173
- After Python changes: `docker compose restart api`
- All PDF ops → `lib/s3_storage.py` (never raw Path in routes)
- All DB ops → `lib/db_operations.py`

## Agents

- **Explore** — delegate multi-file research to avoid cluttering context
- **review** — invoke after plan-based implementation for independent code review
- **FullStackAgent** — full-stack implementation tasks (see `.github/agents/`)

## Reading Order for New Tasks

1. `tasks/lessons.md` — accumulated corrections
2. `CLAUDE.md` — architecture and workflow
3. `lib/db_operations.py` — before any DB work
4. `lib/s3_storage.py` — before any PDF work
5. Relevant route file in `api/routes/`

## Verification

```bash
# API health
curl -s http://localhost:8003/api/health

# DB connection
docker compose exec api python -c "from lib.db import check_connection; print(check_connection())"

# Run diagnose skill for deeper checks
```
