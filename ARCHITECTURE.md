# Architecture

Astrolabe is a battery-research paper management and RAG system built with a **React** frontend and **FastAPI** backend, backed by **PostgreSQL + pgvector** for metadata and vector search.

## Stack

| Layer | Technology | Port |
|-------|-----------|------|
| Frontend | React 19 + Vite | 5173 (dev) |
| Backend API | FastAPI + Uvicorn | 8003 |
| Database | PostgreSQL 16 + pgvector 0.8.0 | 5432 |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | — |
| LLM | Claude (Anthropic API) | — |
| PDF Storage | Local filesystem (`papers/`) | — |

**Current scale:** ~2,018 papers (1,703 with complete metadata), 74,624 cross-references (87.5% with DOIs).

## Directory Structure

```
astrolabe-paper-db/
├── api/                        # FastAPI backend
│   ├── main.py                 # App factory, CORS, router mounting
│   └── routes/                 # Route modules
│       ├── papers.py           # Paper CRUD, stats, filters, references, trash
│       ├── search.py           # Semantic search + RAG (ask Claude)
│       ├── collections.py      # Paper collections management
│       ├── history.py          # Query history + starring
│       ├── settings.py         # App settings + backup/restore
│       ├── discover.py         # Semantic Scholar search + gap analysis + CrossRef
│       └── imports.py          # URL/DOI/upload/metadata-only import + enrichment
│
├── frontend/                   # React SPA
│   └── src/
│       ├── App.jsx             # Routes + layout
│       ├── pages/              # Page components
│       │   ├── Library.jsx     # Main paper table (default route)
│       │   ├── PaperDetail.jsx # Individual paper view + PDF viewer + references
│       │   ├── Dashboard.jsx   # Stats & charts (year, chemistry, journal, topic)
│       │   ├── Collections.jsx # Collection management
│       │   ├── CollectionDetail.jsx
│       │   ├── Research.jsx    # RAG query interface (scoped by collection)
│       │   ├── Discover.jsx    # Semantic Scholar + CrossRef search + gap analysis
│       │   ├── Feed.jsx        # AI-generated blurbs (filters by chemistry/topic/year)
│       │   ├── History.jsx     # Past queries + starring
│       │   ├── Import.jsx      # Bulk import page
│       │   ├── Settings.jsx    # Config + backups
│       │   └── Trash.jsx       # Soft-deleted papers recovery
│       ├── components/         # Shared components
│       │   ├── Layout.jsx      # Sidebar nav + content area
│       │   ├── ImportModal.jsx  # Quick-import dialog
│       │   ├── CommandPalette.jsx # Cmd+K search
│       │   └── Toast.jsx       # Notification system
│       └── services/
│           └── api.js          # All API client functions
│
├── lib/                        # Backend business logic (UI-agnostic)
│   ├── db.py                   # SQLAlchemy engine + session factory (PostgreSQL)
│   ├── db_operations.py        # All PostgreSQL CRUD operations + hybrid search
│   ├── models.py               # SQLAlchemy ORM models (Paper, PaperReference, etc.)
│   ├── crossref.py             # CrossRef API client
│   ├── semantic_scholar.py     # Semantic Scholar API client
│   ├── backup.py               # Backup/restore system
│   ├── journal_normalizer.py   # Journal name normalization
│   ├── jats.py                 # JATS XML abstract cleanup
│   ├── retry.py                # API retry with exponential backoff
│   ├── llm.py                  # Claude API wrapper
│   └── settings_helpers.py     # Settings I/O
│
├── scripts/                    # Standalone CLI tools
│   ├── ingest.py               # PDF → text → chunks → embeddings
│   ├── ingest_pipeline.py      # Staged ingestion pipeline
│   ├── ingest_pipeline_pg.py   # PostgreSQL-native ingestion
│   ├── enrich_pg_bulk.py       # Bulk enrichment (CrossRef + Semantic Scholar)
│   ├── backfill_ref_dois.py    # CrossRef title-search DOI backfill for refs
│   ├── migrate_to_postgres.py  # JSON → PostgreSQL migration (completed)
│   ├── _check_status.py        # Quick enrichment status check
│   ├── _fix_bad_dois.py        # Fix ISSN-as-DOI errors
│   ├── _fix_mdpi_dois.py       # Fix MDPI URL-as-DOI errors
│   └── ...                     # Other maintenance scripts
│
├── tests/                      # pytest test suite
│   └── test_paper_status.py    # 50 tests for paper status classification
│
├── data/                       # Runtime data
│   ├── settings.json           # App configuration
│   └── chroma_db/              # ChromaDB vector store (legacy, being replaced)
│
└── papers/                     # PDF files
```

## API Endpoints

All endpoints are prefixed with `/api/`.

| Group | Endpoints | Module |
|-------|-----------|--------|
| Papers | `GET /papers`, `GET /papers/stats`, `GET /papers/filters`, `GET /papers/charts`, `GET /papers/{filename}`, `PATCH /papers/{filename}/metadata`, `DELETE /papers`, `GET /papers/{filename}/pdf`, `GET /papers/{filename}/references` | `papers.py` |
| Search | `POST /search/chunks`, `POST /search/ask` | `search.py` |
| Collections | CRUD at `/collections`, `/collections/{id}/papers` | `collections.py` |
| History | `GET /history`, `POST /history/{id}/star`, `DELETE /history/{id}` | `history.py` |
| Settings | `GET /settings`, `PATCH /settings`, backup endpoints | `settings.py` |
| Discover | `POST /discover/search`, `GET /discover/gaps` | `discover.py` |
| Import | `POST /import/url`, `/upload`, `/doi`, `/metadata-only`, `/enrich` | `imports.py` |
| Health | `GET /health` | `main.py` |

## Data Flow

```
User (React) → Vite proxy (/api) → FastAPI (port 8003) → PostgreSQL + pgvector
                                                        → Claude API (RAG queries)
                                                        → CrossRef / Semantic Scholar (enrichment + discovery)
```

## Key Design Decisions

- **lib/ is UI-agnostic** — no FastAPI imports. Pure business logic with logging.
- **PostgreSQL + pgvector** for metadata, full-text search, and vector similarity.
- **Paper.filename is the primary key** — not an auto-increment id.
- **PaperReference** stores CrossRef-style reference data with DOI, article_title, author, year, journal_title.
- **Soft delete** via `deleted_at` timestamp on Paper model.
- **Vite proxy** forwards `/api` → `http://localhost:8003` in development.
- **CSS Modules + design tokens** for consistent frontend styling.
- **No async in route handlers** — all database operations are synchronous (SQLAlchemy with psycopg2).

## Running

```bash
# Backend
cd astrolabe-paper-db
python -m uvicorn api.main:app --host 0.0.0.0 --port 8003

# Frontend (separate terminal)
cd frontend
npx vite --port 5173
```

Open http://localhost:5173 in your browser.
