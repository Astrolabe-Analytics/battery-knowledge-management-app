# Architecture

Astrolabe is a battery-research paper management and RAG system built with a **React** frontend and **FastAPI** backend, backed by **PostgreSQL + pgvector** for metadata and vector search.

## Stack

| Layer | Technology | Port |
|-------|-----------|------|
| Frontend | React 19 + Vite | 5173 (dev) |
| Backend API | FastAPI + Uvicorn | 8002 |
| Database | PostgreSQL 16 + pgvector | 5432 |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | — |
| LLM | Claude (Anthropic API) | — |
| PDF Storage | Local filesystem (`papers/`) | — |

## Directory Structure

```
astrolabe-paper-db/
├── api/                        # FastAPI backend
│   ├── main.py                 # App factory, CORS, router mounting
│   └── routes/                 # Route modules
│       ├── papers.py           # Paper CRUD, metadata, references, PDF serving
│       ├── search.py           # Semantic search + RAG (ask Claude)
│       ├── collections.py      # Paper collections management
│       ├── history.py          # Query history + starring
│       ├── settings.py         # App settings + backup/restore
│       ├── discover.py         # Semantic Scholar search + gap analysis
│       └── imports.py          # URL/DOI/upload/metadata-only import
│
├── frontend/                   # React SPA
│   └── src/
│       ├── App.jsx             # Routes + layout
│       ├── pages/              # Page components
│       │   ├── Library.jsx     # Main paper table (default route)
│       │   ├── PaperDetail.jsx # Individual paper view + PDF viewer
│       │   ├── Dashboard.jsx   # Stats & charts
│       │   ├── Collections.jsx # Collection management
│       │   ├── CollectionDetail.jsx
│       │   ├── Research.jsx    # RAG query interface
│       │   ├── Discover.jsx    # Semantic Scholar + gap analysis
│       │   ├── Feed.jsx        # AI-generated blurbs
│       │   ├── History.jsx     # Past queries
│       │   └── Settings.jsx    # Config + backups
│       └── components/         # Shared components
│           ├── Layout.jsx      # Sidebar nav + content area
│           ├── ImportModal.jsx  # Import dialog
│           ├── CommandPalette.jsx
│           └── Toast.jsx
│
├── lib/                        # Backend business logic (UI-agnostic)
│   ├── db.py                   # SQLAlchemy engine + session factory
│   ├── db_operations.py        # All PostgreSQL CRUD operations
│   ├── models.py               # SQLAlchemy ORM models
│   ├── rag.py                  # ChromaDB, embeddings, vector search
│   ├── app_helpers.py          # CrossRef queries, metadata ops
│   ├── library_operations.py   # Paper import pipeline, soft delete
│   ├── enrichment.py           # CrossRef/Semantic Scholar enrichment
│   ├── semantic_scholar.py     # Semantic Scholar API client
│   ├── gap_analysis.py         # Citation gap detection
│   ├── collections.py          # SQLite collections (legacy)
│   ├── backup.py               # Backup/restore system
│   ├── journal_normalizer.py   # Journal name normalization
│   ├── jats.py                 # JATS XML abstract cleanup
│   ├── retry.py                # API retry utilities
│   └── ...                     # Other utilities
│
├── scripts/                    # Standalone CLI tools
│   ├── ingest.py               # PDF → text → chunks → embeddings
│   ├── ingest_pipeline.py      # Staged ingestion pipeline
│   ├── enrich_crossref_bulk.py # Bulk CrossRef enrichment
│   ├── migrate_to_postgres.py  # JSON → PostgreSQL migration
│   └── ...                     # Maintenance & fix scripts
│
├── data/                       # Runtime data
│   ├── metadata.json           # Paper metadata (2,022 papers)
│   ├── settings.json           # App configuration
│   ├── chroma_db/              # ChromaDB vector store
│   └── ...
│
└── papers/                     # PDF files
```

## API Endpoints

All endpoints are prefixed with `/api/`.

| Group | Endpoints | Module |
|-------|-----------|--------|
| Papers | `GET /papers`, `GET /papers/{filename}`, `PATCH /papers/{filename}/metadata`, `DELETE /papers`, `GET /papers/{filename}/pdf`, `GET /papers/{filename}/references` | `papers.py` |
| Search | `POST /search/chunks`, `POST /search/ask` | `search.py` |
| Collections | CRUD at `/collections`, `/collections/{id}/papers` | `collections.py` |
| History | `GET /history`, `POST /history/{id}/star`, `DELETE /history/{id}` | `history.py` |
| Settings | `GET /settings`, `PATCH /settings`, backup endpoints | `settings.py` |
| Discover | `POST /discover/search`, `GET /discover/gaps` | `discover.py` |
| Import | `POST /import/url`, `/upload`, `/doi`, `/metadata-only`, `/enrich` | `imports.py` |
| Health | `GET /health` | `main.py` |

## Data Flow

```
User (React) → Vite proxy (/api) → FastAPI (port 8002) → PostgreSQL + pgvector
                                                        → ChromaDB (embeddings)
                                                        → Claude API (RAG queries)
                                                        → CrossRef/Semantic Scholar (enrichment)
```

## Key Design Decisions

- **lib/ is UI-agnostic** — no Streamlit, no FastAPI imports. Pure business logic with logging.
- **PostgreSQL + pgvector** for metadata, full-text search, and vector similarity (replacing JSON files + ChromaDB).
- **Vite proxy** forwards `/api` → `http://localhost:8002` in development.
- **CSS Modules + design tokens** for consistent frontend styling.
- **No async in route handlers** — all database operations are synchronous (SQLAlchemy with psycopg2).

## Running

```bash
# Backend
cd astrolabe-paper-db
uvicorn api.main:app --host 127.0.0.1 --port 8002 --reload

# Frontend (separate terminal)
cd frontend
npx vite --port 5173
```

Open http://localhost:5173 in your browser.

All without modifying `lib/rag.py`.
