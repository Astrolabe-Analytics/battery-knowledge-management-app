---
description: "Use when modifying the FastAPI server, adding routes, or working with PostgreSQL/pgvector queries and S3/PDF operations."
applyTo: "api/**, lib/**"
---

# Backend — FastAPI + SQLAlchemy + pgvector

## Route Structure

`api/main.py` is the entry point. It mounts 7 route modules at `/api/*`. Route handlers stay thin — business logic lives in `lib/`.

| Module | Prefix | Covers |
|--------|--------|--------|
| `papers.py` | `/api/papers` | CRUD, PDF serving, metadata, notes, read status |
| `search.py` | `/api/search` | RAG pipeline, semantic search |
| `imports.py` | `/api/import` | URL/DOI/PDF upload, enrichment with SSE |
| `collections.py` | `/api/collections` | Collection CRUD |
| `history.py` | `/api/history` | Query history |
| `settings.py` | `/api/settings` | App settings |
| `discover.py` | `/api/discover` | Discovery features |

## Database Access

All reads and writes go through `lib/db_operations.py`. Never write SQLAlchemy inline in routes.

## PDF Operations

**ALWAYS** use `lib/s3_storage.py`. Never use raw `Path("papers")` in route handlers.

```python
from lib.s3_storage import pdf_exists, save_pdf, get_presigned_url, is_s3_mode

has_pdf = pdf_exists(filename)          # local or S3
save_pdf(filename, content_bytes)       # saves locally + uploads to S3 in s3 mode
if is_s3_mode():
    return RedirectResponse(get_presigned_url(filename))
```

Why: ECS Fargate has no persistent local storage. Raw filesystem writes silently break in production.

## After Changes

```bash
docker compose restart api
docker compose logs api --tail=30
```
