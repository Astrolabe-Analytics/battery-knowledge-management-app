# Astrolabe Product Roadmap
## From Research Library to Data Analytics Platform

---

## Current State

### What's Built (Paper Database — Phase 2 of Flywheel)
- **2,100+ papers** indexed with metadata (title, authors, year, journal, DOI, chemistry, topics)
- **242 papers with PDFs** (up from 44 after bulk download)
- **AI summaries** for 10 papers (template proven, ready to scale)
- **Research feed** — tweet-style paper blurbs for quick scanning
- **RAG pipeline** — semantic search + hybrid search + reranking + cited Q&A
- **CSV import** — Notion exports, Battery Datasets catalog, with duplicate detection and enrichment
- **Metadata enrichment** — CrossRef, Semantic Scholar, Unpaywall waterfall
- Built in Streamlit, single-user, local only

### What Hasn't Started
- **Data pipeline** (Phase 1): 334 datasets undownloaded
- **Feature extraction** (Phase 1): dQ/dV, EIS, capacity fade — untouched
- **Pattern discovery** (Phase 3): Cross-dataset analysis — untouched
- **Model development** (Phase 4): SOH/SOC/RUL models — untouched
- **Team access**: No multi-user, no shared deployment

---

## Deliverable Products

Four user-facing artifacts, all sharing a common platform:

| Product | Description | Primary Users |
|---------|-------------|---------------|
| **Research Feed** | Tweet-style AI paper summaries, filterable, scrollable | Whole team, external audience |
| **Reference Manager** | Library, detail view, import, RAG Q&A — Mendeley on steroids | Researchers |
| **Dataset Catalog** | Browseable catalog of 334+ battery datasets with metadata | Researchers, engineers |
| **Analytics Platform** | SOH/SOC/RUL models, benchmarks, algorithm matching | Engineers, customers |

---

## Dependency Map

```
Platform Foundation (React / FastAPI / Postgres + pgvector)
    │
    ├── Research Library + Feed (paper apps)
    │       └── AI summaries at scale
    │
    ├── Dataset Catalog (browsing + search)
    │       └── Data Pipeline (download, normalize, store)
    │               └── Feature Extraction (dQ/dV, EIS, capacity)
    │
    └── Analytics Product
            ├── needs Literature insights (from papers)
            └── needs Data + Features (from pipeline)
                    ├── Pattern Discovery
                    ├── Model Development (SOH/SOC/RUL)
                    └── Benchmark & Validate
```

---

## Workstream 1: Platform Foundation (Weeks 1–4)

**Goal:** Shared infrastructure that all products build on. This is the enabler for team access and everything downstream.

### Deliverables
- [ ] FastAPI backend with REST endpoints for all operations
- [ ] Postgres + pgvector as single database (replaces metadata.json + ChromaDB)
- [ ] Authentication / multi-user support
- [ ] React frontend shell with routing
- [ ] Deploy to cloud (team can access)
- [ ] CI/CD pipeline

### Key API Endpoints
```
POST   /api/papers/import/csv       — CSV import with duplicate detection
POST   /api/papers/import/url       — Import from URL (arXiv, DOI, publisher)
POST   /api/papers/import/pdf       — Upload PDF directly
GET    /api/papers                   — List/filter papers
GET    /api/papers/{id}              — Paper detail with metadata
PUT    /api/papers/{id}              — Update metadata
DELETE /api/papers/{id}              — Delete paper
POST   /api/papers/{id}/enrich      — Trigger enrichment (CrossRef/S2/Unpaywall)
POST   /api/papers/{id}/summarize   — Generate AI summary
POST   /api/search                   — RAG search with citations
GET    /api/stats                    — Library statistics
GET    /api/feed                     — Research feed (papers with blurbs)
```

### Tech Stack
| Component | Technology |
|-----------|-----------|
| Backend | FastAPI (Python) |
| Database | Postgres + pgvector |
| Frontend | React + Tailwind |
| Auth | TBD (simple JWT to start) |
| Hosting | TBD (AWS, Railway, Fly.io) |
| Background jobs | Celery or FastAPI background tasks |

### Migration Reference Docs
- `CSV_IMPORT_MIGRATION_GUIDE.md` — All hard-won lessons from V1
- `DEVELOPMENT_LESSONS_LEARNED.md` — Claude Code patterns, Streamlit traps, data integrity rules
- `CANONICAL_SCHEMA.md` — Paper metadata schema

---

## Workstream 2: Research Library + Feed (Weeks 2–6)

**Goal:** Rebuild the paper-facing apps on React. Team can browse, add, query, and discover papers.

### Reference Manager (Mendeley on Steroids)
- [ ] Library table — sortable, filterable, fast (no AG Grid issues)
- [ ] Paper detail view — compact bibliographic header, AI summary, abstract, collapsible sections
- [ ] CSV import with progress tracking (background job, not blocking UI)
- [ ] URL import (arXiv, DOI, publisher pages)
- [ ] PDF upload with automatic parsing + chunking + embedding
- [ ] Metadata editing (inline DOI edit, enrichment button)
- [ ] RAG Q&A with cited answers and click-through to source chunks
- [ ] Duplicate detection on import
- [ ] Collections / tagging

### Research Feed
- [ ] Scrollable timeline of AI-summarized papers
- [ ] 280-char blurbs with "Read Full Summary" expand
- [ ] Filter by chemistry, topic, year
- [ ] Click through to full detail view
- [ ] Potentially public-facing (good content marketing for Astrolabe)

### Scale AI Summaries
- [ ] Generate summaries for all 242 papers with PDFs
- [ ] Generate feed blurbs for all summarized papers
- [ ] Abstract extraction for papers where CrossRef didn't provide one
- [ ] Estimated cost: ~$50–100 for 242 papers via Claude API

---

## Workstream 3: Data Pipeline + Catalog (Weeks 4–10)

**Goal:** Download, normalize, and catalog the 334 battery datasets. Build a browseable catalog app.

### Dataset Download (Phase 1.1 of Flywheel)
- [ ] Implement downloaders by repository:
  - Zenodo (79) — API + zenodo_get
  - Mendeley (67) — API
  - Figshare (11) — API
  - OSF (9) — API
  - GitHub (10) — git clone
  - IEEE Dataport (21) — needs auth
  - Direct downloads (22) — wget/custom
  - Institutional (46) — case by case
  - Manual triage (69) — investigate first
- [ ] Download tracking database (status, retries, checksums)
- [ ] ~500GB–1.5TB raw data organized by source

### Data Normalization (Phase 1.2 of Flywheel)
- [ ] Design standardized schema (time, voltage, current, temperature, capacity, cycle, cell_id, chemistry)
- [ ] Build ETL for most common formats (.mat, .csv, .xlsx, .h5)
- [ ] Output: Parquet files with consistent schema
- [ ] Bronze/Silver/Gold data lake structure

### Feature Extraction (Phase 1.3 of Flywheel)
- [ ] Capacity per cycle, coulombic efficiency
- [ ] dQ/dV curves (differential capacity)
- [ ] EIS features (R0, Rct, Warburg)
- [ ] Capacity fade rate, resistance growth
- [ ] Knee point detection
- [ ] Output: Feature store (queryable table per cell per cycle)

### Dataset Catalog App
- [ ] Browseable catalog of all 334+ datasets
- [ ] Filter by chemistry, test type, source, size
- [ ] Dataset detail view (description, conditions, download link, related papers)
- [ ] Connect datasets to papers (link catalog entries to paper database)
- [ ] Search across datasets

---

## Workstream 4: Analytics Product (Weeks 8–12+)

**Goal:** The actual Astrolabe value proposition — battery state estimation models, benchmarks, algorithm matching.

### Pattern Discovery (Phase 3 of Flywheel)
- [ ] Cross-chemistry comparison (LFP vs NMC vs NCA degradation patterns)
- [ ] Cross-condition analysis (temperature, C-rate effects)
- [ ] Feature correlation study (what predicts SOH best?)
- [ ] Degradation signature clustering
- [ ] Document findings in knowledge base

### Model Development (Phase 4 of Flywheel)
- [ ] Baseline models:
  - Coulomb counting (SOC)
  - Linear capacity fade (SOH)
  - Exponential degradation (RUL)
  - SOH from resistance
- [ ] ML models (2–3 from literature review):
  - LSTM for SOC estimation
  - Transformer/CNN for SOH from cycling history
  - Gaussian process for degradation modeling
  - Early-life RUL prediction (Severson et al. approach)
- [ ] Validation framework:
  - K-fold CV within dataset
  - Cross-dataset validation
  - Temporal validation (train early, predict late)
  - Benchmark evaluation on curated datasets

### Benchmark Curation
- [ ] SOH-Bench: Clean labels, multiple chemistries, varied conditions
- [ ] SOC-Bench: Dynamic profiles, multiple temperatures
- [ ] RUL-Bench: Full lifetime data, known EOL
- [ ] Transfer-Bench: Matched conditions, different chemistries
- [ ] Leaderboard comparing published methods

### Algorithm-Dataset Matching Engine
- [ ] Given a dataset, recommend best algorithms from literature
- [ ] Given an algorithm, recommend best datasets to validate on
- [ ] Powered by literature mining + benchmark results

---

## Rough Timeline

```
Week  1  2  3  4  5  6  7  8  9  10  11  12
      ├──────────────┤
      Platform Foundation (React/FastAPI/Postgres)
         ├─────────────────┤
         Research Library + Feed (React rebuild)
                  ├──────────────────────────┤
                  Data Pipeline + Catalog
                              ├────────────────────────┤
                              Analytics Product
```

### Key Milestones
| Week | Milestone |
|------|-----------|
| 2 | FastAPI + Postgres running, basic paper CRUD |
| 4 | React library app deployed, team can access |
| 6 | AI summaries for all 242 papers, feed live |
| 6 | First 50 datasets downloaded and cataloged |
| 8 | Dataset catalog app live, 150+ datasets normalized |
| 10 | Feature store populated, pattern analysis started |
| 12 | First baseline models trained, benchmark results |

---

## Open Decisions

1. **Hosting:** AWS (most flexible, aligns with S3 data lake) vs. simpler platforms (Railway, Fly.io) for the web apps?
2. **Team size:** Who else is contributing? Affects auth complexity and collaboration features.
3. **Public-facing feed:** Is the research feed public (content marketing) or internal only?
4. **Chemistry priority:** Focus on LFP + NMC first for data pipeline, or try to cover everything?
5. **Compute budget:** Constraints on AWS spend for data storage, processing, model training?
6. **AI summary cost tolerance:** ~$50–100 for 242 papers, ~$500+ for all 2,100 (if PDFs acquired). Worth it?
