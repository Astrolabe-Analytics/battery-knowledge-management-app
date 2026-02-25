# Astrolabe — Battery Research Paper Database

A full-stack paper management and RAG (Retrieval-Augmented Generation) system for battery research, built with React + FastAPI + PostgreSQL/pgvector.

**GitHub:** https://github.com/Astrolabe-Analytics/battery-knowledge-management-app/

## Features

- **Library** — Browse, search, filter ~2,000 battery research papers with sortable table
- **Paper Detail** — View metadata, abstract, PDF, and cross-references with DOI links
- **Research (RAG)** — Ask natural-language questions answered by Claude with source citations from your papers
- **Discover** — Search Semantic Scholar + CrossRef for new papers, gap analysis
- **Dashboard** — Charts showing papers by year, chemistry, journal, topic
- **Collections** — Organize papers into named collections, scope RAG queries by collection
- **Feed** — Browse AI-generated paper summaries filtered by chemistry/topic/year
- **Import** — Add papers via URL, DOI, PDF upload, or metadata-only entry
- **History** — View and star past RAG queries

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + Vite + CSS Modules |
| Backend | FastAPI + Uvicorn (Python 3.13) |
| Database | PostgreSQL 16 + pgvector 0.8.0 |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 (local) |
| LLM | Claude via Anthropic API |
| External APIs | CrossRef, Semantic Scholar |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16 with pgvector extension
- Anthropic API key

### 1. Clone and install

```bash
git clone https://github.com/Astrolabe-Analytics/battery-knowledge-management-app.git
cd battery-knowledge-management-app
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### 2. Set up environment

Create a `.env` file:
```
ANTHROPIC_API_KEY=your-key-here
SEMANTIC_SCHOLAR_API_KEY=your-key-here  # optional, higher rate limits
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/astrolabe
```

### 3. Set up database

```sql
CREATE DATABASE astrolabe;
\c astrolabe
CREATE EXTENSION vector;
```

### 4. Run

```bash
# Backend (terminal 1)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8003

# Frontend (terminal 2)
cd frontend
npx vite --port 5173
```

Open http://localhost:5173

## RAG Pipeline

The Research page uses a multi-stage retrieval pipeline:

1. **Query Expansion** — Claude expands your question with related technical terms
2. **Hybrid Search** — Combines pgvector semantic similarity + BM25 keyword matching
3. **Reranking** — Claude reorders candidates by relevance, selects top results
4. **Answer Generation** — Claude synthesizes an answer with citations to specific papers

## Project Structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for full details.

```
├── api/routes/       # FastAPI route handlers
├── lib/              # Business logic (DB ops, CrossRef, Semantic Scholar)
├── frontend/src/     # React SPA (pages, components, services)
├── scripts/          # CLI tools (ingestion, enrichment, maintenance)
├── tests/            # pytest test suite
└── papers/           # PDF files
```

## Scripts

Key CLI tools in `scripts/`:

| Script | Purpose |
|--------|---------|
| `ingest_pipeline_pg.py` | Ingest PDFs → text → chunks → embeddings into PostgreSQL |
| `enrich_pg_bulk.py` | Bulk metadata enrichment via CrossRef + Semantic Scholar |
| `backfill_ref_dois.py` | Find missing DOIs for paper references via CrossRef title search |
| `_check_status.py` | Quick check of enrichment completeness |

## Tests

```bash
pytest tests/ -v
```

Currently 50 tests covering paper status classification logic.

## License

Private — Astrolabe Analytics
