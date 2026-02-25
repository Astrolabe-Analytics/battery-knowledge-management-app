# Astrolabe Paper Database — Roadmap & Development Plan

## Where We Are Now (February 2026)

**~2,018 papers** in PostgreSQL (1,703 with complete metadata, 315 still need enrichment). **74,624 cross-references** stored (87.5% with DOIs after backfill). Full React + FastAPI + PostgreSQL/pgvector stack. All major pages built and functional.

**GitHub:** https://github.com/Astrolabe-Analytics/battery-knowledge-management-app/

**What's working:**
- React frontend with Library, PaperDetail, Dashboard, Research (RAG), Discover, Collections, Feed, History, Import, Settings, Trash pages
- FastAPI backend with full CRUD, search, enrichment, and import APIs
- PostgreSQL + pgvector for metadata and vector search
- RAG pipeline: query expansion → hybrid search → reranking → Claude answer
- Bulk enrichment via CrossRef + Semantic Scholar
- Reference DOI backfill (2,811 DOIs recovered via CrossRef title search)
- Paper status classification: AI Summary / Complete / Metadata Only / Incomplete
- Google Scholar fallback links for references without DOIs
- [J] citation artifact cleanup from API responses
- 50 pytest tests for status classification

---

## Completed Phases

### ~~Phase 1: Stabilize~~ ✅
- ✅ Fixed duplicate detection (title normalization)
- ✅ Fixed UI bugs (checkbox, navigate trigger column, DOI edit, notifications)
- ✅ Big Notion CSV import (~1,600+ papers)
- ✅ Batch metadata enrichment (CrossRef + Semantic Scholar)
- ✅ Pushed to GitHub

### ~~Phase 2: Make It Useful~~ ✅ (Partial)
- ✅ Monolith extraction → complete rewrite as React + FastAPI
- ✅ Collection-scoped RAG queries (Research page)
- ❌ Multi-paper synthesis (not yet built)
- ❌ Auto-summarize on ingest (only 5 papers have AI summaries)
- ❌ Connect to dataset catalog (not yet started)

### ~~Phase 3: Infrastructure Migration~~ ✅
- ✅ FastAPI backend (all routes)
- ✅ PostgreSQL + pgvector (full migration from JSON + ChromaDB + SQLite)
- ✅ React frontend (all pages, CSS Modules, design tokens)
- ❌ Docker deploy (still running locally)

---

## Phase 4: Scale & Polish (Current Focus)

*Goal: Improve data quality, add research-grade features, prepare for production.*

### 4.1 Metadata Enrichment (In Progress)
- ✅ Bulk CrossRef enrichment via `scripts/enrich_pg_bulk.py`
- ✅ Reference DOI backfill (2,811 DOIs recovered)
- 🔄 Ongoing: ~315 papers still need enrichment (21 have DOI, 214 have URL, 80 title-only)
- ❌ Alembic migrations (manual schema changes for now)

### 4.2 Research Page Filters
Add chemistry, topic, and year-range dropdowns to the Research page alongside the collection picker. Filter data already exists (Dashboard charts use it). This is the single biggest RAG quality improvement.

### 4.3 AI Summaries at Scale
Only 5 papers have `ai_summary`. Generate summaries for the ~1,700 complete papers to make the Feed page useful. Requires batched Claude API calls.

### 4.4 Multi-Paper Comparison
Select 2–5 papers and ask a question. Only search chunks from those papers. Prompt Claude to compare and contrast what each paper says, noting agreements and disagreements.

### 4.5 Citation Graph
With 74K+ references stored, build an interactive visualization showing which papers in the library cite each other. Enables "find all papers that cite Severson et al. 2019."

### 4.6 Figure/Image Handling
Extract figures from PDFs, use Claude vision to describe them, embed descriptions as searchable chunks. Return relevant figures alongside text answers.

### 4.7 Dataset Catalog Connection
Import the Battery Datasets catalog and cross-reference with the paper library. Show "Associated Datasets" on paper detail pages. New Datasets tab.

### 4.8 Automated Ingestion
- RSS feeds from arXiv categories and journal ToCs
- Zotero sync (watch for new additions)
- Automatic deduplication, enrichment, and indexing

### 4.9 Domain-Specific Embeddings
Fine-tune an embedding model on battery literature so "capacity fade" and "SOH degradation" are closely related. Improves retrieval at scale.

### 4.10 Docker Deployment
Docker Compose with frontend, backend, postgres containers. Deploy to VPS or managed hosting.

---

## Priority Matrix (Updated February 2026)

| Priority | Task | Impact | Effort | Status |
|----------|------|--------|--------|--------|
| **P0** | ~~Fix duplicate detection~~ | High | Low | ✅ Done |
| **P0** | ~~Big Notion import~~ | High | Low | ✅ Done |
| **P0** | ~~FastAPI + React + PostgreSQL migration~~ | High | High | ✅ Done |
| **P1** | ~~Batch metadata enrichment~~ | High | Low | ✅ Done (ongoing) |
| **P1** | ~~Reference DOI backfill~~ | Medium | Medium | ✅ Done (87.5% coverage) |
| **P1** | Research page filters (chemistry/topic/year) | High | Low | Not started |
| **P1** | Batch AI summary generation | High | Medium | Not started |
| **P1** | Finish remaining enrichment (~315 papers) | Medium | Low | In progress |
| **P2** | Multi-paper comparison | High | Medium | Not started |
| **P2** | Citation graph visualization | Medium | High | Not started |
| **P2** | Connect to dataset catalog | High | Medium | Not started |
| **P2** | More tests (API routes, search, import) | Medium | Medium | Not started |
| **P3** | Docker deployment | Medium | Medium | Not started |
| **P3** | Alembic migrations | Low | Medium | Not started |
| **P3** | Codebase cleanup (stale files/docs) | Low | Low | Not started |
| **P4** | Figure/image extraction | Medium | High | Not started |
| **P4** | Automated ingestion (RSS, Zotero) | Medium | High | Not started |
| **P4** | Domain-specific embeddings | Medium | High | Not started |

---

## Decision Log

| Decision | Rationale | Date |
|----------|-----------|------|
| React + FastAPI + PostgreSQL | Replaced Streamlit + JSON + ChromaDB + SQLite | Jan 2026 |
| Paper.filename as primary key | Stable identifier, matches filesystem | Jan 2026 |
| pgvector over ChromaDB | Single database, better scaling with PostgreSQL | Jan 2026 |
| Soft delete via `deleted_at` | Recoverable deletes without data loss | Jan 2026 |
| CrossRef + Semantic Scholar dual enrichment | CrossRef for DOI/journal data, S2 for citations/abstracts | Jan 2026 |
| Local sentence-transformers | Free, no API costs; upgrade to domain-specific later | 2025 |
| Don't rebuild Zotero | Focus on RAG/AI capabilities, not reference management | 2025 |
| Semantic Scholar API key | Higher rate limits (1 req/sec) | 2025 |
