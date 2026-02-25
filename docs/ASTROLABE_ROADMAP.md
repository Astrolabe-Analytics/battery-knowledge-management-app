# Astrolabe Paper Database — Roadmap & Development Plan

## Where You Are Now

**173 papers** ingested (6 with PDFs, rest metadata-only). Working RAG pipeline with hybrid search, query expansion, and reranking. Streamlit UI with Library/Discover/Research/Import tabs. Multipage structure started but app_monolith.py (5,957 lines) still runs most of the app. Library page extracted and fast; other pages still slow.

**GitHub:** https://github.com/Astrolabe-Analytics/battery-knowledge-management-app/

**Known bugs:**
- Duplicate detection failing on CSV import (title normalization issue)
- Enrichment stats not updating after enrichment runs
- Library table checkbox navigates to detail view instead of just selecting
- "navigate trigger" column appearing in table
- DOI edit pencil broken
- Flash notification on DOI update firing on every rerun

---

## Phase 1: Stabilize (This Week)

*Goal: Fix what's broken, load your papers, make the tool usable for daily research.*

### 1.1 Fix Duplicate Detection (BLOCKING)
The big Notion CSV import (1,400+ papers) can't happen until this works. The issue is title normalization — stored titles and CSV titles differ in whitespace, encoding, or special characters.

**Prompt for Claude Code:**
```
Diagnose the duplicate detection failure. Pick 5 papers already in metadata.json, simulate re-importing them from CSV, and print the exact title strings character by character from both sources. Show me why the match is failing — is it whitespace, encoding, unicode, truncation, or case? Then fix the normalization so it handles all of these. Test by importing a CSV with 10 known duplicates and verify all 10 are skipped.
```

### 1.2 Fix Remaining UI Bugs
These are small but annoying. Give Claude Code one prompt with all of them:

```
Fix these UI bugs in the Library page:

1. Checkbox click navigates to detail view — it should only toggle selection
2. A "navigate trigger" column is appearing in the table — remove it
3. DOI edit pencil icon is broken — nothing happens when clicked
4. A DOI update notification flashes on every page rerun even when nothing was edited
5. "Enrich Metadata" button says success but library stats don't update after refresh

Find and fix each one. Test before telling me it's done.
```

### 1.3 Big Import
Once duplicate detection works:

```
Import the full Notion CSV export (1,634 papers). Use batch processing (batches of 20). Log progress, skip duplicates, save metadata-only for papers without PDFs. Show a summary at the end: how many imported, how many skipped as duplicates, how many failed.
```

Then enrich metadata in batches:
```
Enrich all papers that are missing DOI, authors, year, or journal. Process in batches of 10 with 2-second delays between CrossRef calls. Use Semantic Scholar as fallback (1 request/second with API key). Show progress and summary.
```

### 1.4 Push to GitHub
After every session. No exceptions.

---

## Phase 2: Make It Useful (Weeks 2–3)

*Goal: Turn it from a demo into a tool you actually use for research.*

### 2.1 Complete Monolith Extraction
Extract remaining pages from app_monolith.py one at a time. Same approach that worked for Library:

| Page | Estimated Size | Priority |
|------|---------------|----------|
| Detail view | ~800 lines | High (navigated to constantly) |
| Research/Query tab | ~600 lines | High (core feature) |
| Import tab | ~500 lines | Medium |
| Discover tab | ~400 lines | Medium |
| Settings/History/Trash | ~300 lines each | Low |

For each page:
```
Extract the [TAB NAME] from app_monolith.py into pages/[filename].py. Move all helper functions it needs into lib/ modules. The page must NOT import app_monolith. Test that it works independently.
```

After all pages are extracted, delete app_monolith.py.

### 2.2 RAG Quality Improvements
These make your query results actually good enough to trust for research:

**Filter queries by metadata** — search only papers matching a chemistry, topic, year range, or collection. This is the single biggest quality improvement for a growing corpus.

```
Add metadata filtering to the Research tab query. Before running a query, let me optionally select: chemistry (dropdown), topic tags (multi-select), year range (slider), and collection (dropdown). Pass these filters to ChromaDB's where= parameter so only matching chunks are searched. This dramatically improves relevance when I'm researching a specific topic.
```

**Multi-paper synthesis** — compare what multiple papers say about a topic.

```
Add a "Compare Papers" feature. Let me select 2-5 papers from the library, then ask a question. Only search chunks from those specific papers. The prompt to Claude should explicitly ask it to compare and contrast what each paper says, noting agreements and disagreements.
```

**Auto-summarize on ingest** — when a new paper is added with a PDF, generate a 3-sentence summary and store it.

```
When a paper is ingested with a PDF, use Claude to generate a 3-sentence summary from the abstract and introduction. Store it in the metadata as "ai_summary". Display it on the detail page and in the library table as a tooltip on hover.
```

### 2.3 Connect to Dataset Catalog
This is the Astrolabe flywheel connection — linking papers to datasets.

```
Import the Battery Datasets catalog (battery_datasets_catalog_jan17_2026.xlsx) and cross-reference it with the paper library. For each dataset that has a paper_url matching a paper in the library, create a link between them. On the paper detail page, show "Associated Datasets" with links. On a new Datasets tab, show the catalog with links back to papers.
```

---

## Phase 3: Infrastructure Migration (Weeks 4–6)

*Goal: Move from Streamlit to a real web app. This is the "throw away the UI" step.*

### 3.1 Why Move Off Streamlit

Streamlit will always have these problems:
- Every click reruns the entire script (0.5–2s delay)
- No real state management (session_state is fragile)
- Limited interactivity (no proper click handlers, no drag-and-drop)
- Can't deploy easily for multiple users
- Looks like a prototype no matter how much CSS you add

### 3.2 What Carries Over (Everything That Matters)

Your backend code transfers almost directly:

| Component | Current | Production | Migration Effort |
|-----------|---------|-----------|-----------------|
| PDF parsing | pymupdf4llm | Same | None |
| Chunking | lib/chunking.py | Same | None |
| Vector DB | ChromaDB | pgvector or Qdrant | Moderate |
| Metadata store | metadata.json | PostgreSQL | Moderate |
| Embeddings | sentence-transformers | Same (or upgrade) | Low |
| DOI extraction | lib/enrichment.py | Same | None |
| CrossRef/Semantic Scholar | lib/enrichment.py | Same | None |
| RAG pipeline | lib/rag.py, lib/search.py | Same | Low |
| Claude API calls | lib/ modules | Same | None |

What gets thrown away: all Streamlit code (app.py, pages/*.py, AG Grid config, st.session_state logic).

### 3.3 Target Architecture

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND                          │
│              React + TypeScript                      │
│                                                      │
│   Library Table ── Detail View ── Query Interface    │
│   Import Panel ── Discover ── Collections            │
│                                                      │
│   Tailwind CSS · shadcn/ui components                │
│   TanStack Table (replaces AG Grid)                  │
│   React Router (instant page navigation)             │
└────────────────────┬────────────────────────────────┘
                     │ REST API (JSON)
                     │
┌────────────────────┴────────────────────────────────┐
│                    BACKEND                            │
│                FastAPI (Python)                       │
│                                                      │
│   /api/papers ── /api/query ── /api/import           │
│   /api/enrich ── /api/collections ── /api/discover   │
│                                                      │
│   lib/rag.py · lib/enrichment.py · lib/search.py     │
│   (your existing backend code, mostly unchanged)     │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────┐
│                    DATA LAYER                         │
│                                                      │
│   PostgreSQL (metadata + pgvector for embeddings)    │
│   S3 or local disk (PDFs)                            │
│   Redis (optional, for caching)                      │
└─────────────────────────────────────────────────────┘
```

### 3.4 Migration Steps

**Step 1: Build FastAPI backend (1–2 weekends)**

Wrap your existing lib/ functions in API endpoints. This is mostly mechanical.

```python
# Example: your existing code becomes an API endpoint

from fastapi import FastAPI
from lib.rag import query_papers
from lib.enrichment import enrich_paper

app = FastAPI()

@app.get("/api/papers")
def list_papers(chemistry: str = None, topic: str = None):
    papers = get_all_papers()
    if chemistry:
        papers = [p for p in papers if chemistry in p.get("chemistries", [])]
    return papers

@app.post("/api/query")
def query(question: str, filters: dict = None):
    return query_papers(question, filters)

@app.post("/api/papers/{paper_id}/enrich")
def enrich(paper_id: str):
    return enrich_paper(paper_id)
```

**Step 2: Replace metadata.json with PostgreSQL (1 weekend)**

metadata.json doesn't scale and has no concurrent access. Move to Postgres with pgvector extension so you get metadata + vector search in one database (eliminating ChromaDB).

**Step 3: Build React frontend (2–3 weekends)**

Use a component library like shadcn/ui so you're not designing from scratch. Navigation is instant. Table interactions work properly. No more fighting Streamlit.

**Step 4: Deploy (1 weekend)**

Docker Compose with three containers: frontend, backend, postgres. Deploy to a cheap VPS (Hetzner, DigitalOcean) or Railway/Render for managed hosting.

### 3.5 Alternative: Gradual Migration

If a full rewrite feels too risky, you can migrate incrementally:

1. Build FastAPI backend alongside Streamlit (both read from same data)
2. Build React frontend that talks to FastAPI
3. Once React frontend works, stop using Streamlit
4. Delete Streamlit code

This way you always have a working system.

---

## Phase 4: Scale & Polish (Months 2–3)

*Goal: Handle 5,000+ papers, multiple users, and production-grade reliability.*

### 4.1 Figure/Image Handling
Extract figures from PDFs, use Claude vision to describe them, embed descriptions as searchable chunks. Return relevant figures alongside text answers.

### 4.2 Citation Graph
Extract references from each paper, cross-reference against your library. Build a graph showing which papers cite which. Enable queries like "find all papers that cite Severson et al. 2019."

### 4.3 Automated Ingestion
- Slack bot watches channels for paper links
- RSS feeds from arXiv categories and journal ToCs
- Zotero sync (watch for new additions)
- Automatic deduplication, metadata enrichment, and indexing

### 4.4 Domain-Specific Embeddings
Fine-tune an embedding model on battery literature so it understands that "capacity fade" and "SOH degradation" are closely related. This improves retrieval quality significantly at scale.

### 4.5 Knowledge Graph Layer
Extract entities and relationships from papers (Cell X → tested at → Temp Y → showed → Degradation Rate Z). Enables structured queries that pure semantic search can't handle.

---

## Software Development Practices You Should Adopt

These are things that will save you time and prevent bugs, roughly in order of importance.

### 1. Git Discipline
You're already using git, but tighten it up:

- **Commit often** with descriptive messages (not "fix stuff")
- **Never commit on main** — create a branch for each feature, merge when it works
- **Push daily** — your laptop is a single point of failure
- **Tag releases** — when something works well, `git tag v0.1.0` so you can always get back to it

```bash
# Feature branch workflow
git checkout -b fix-duplicate-detection
# ... do the work ...
git add -A && git commit -m "fix title normalization in duplicate detection"
git checkout main && git merge fix-duplicate-detection
git push
```

### 2. Environment Management
You've been bitten by this already (API keys, env variables). Lock it down:

- **`.env` file** for all secrets (API keys, database URLs)
- **`.env.example`** in the repo showing what variables are needed (without values)
- **`python-dotenv`** loads them automatically
- **Never hardcode secrets** — not even temporarily
- **requirements.txt** or better, **`pyproject.toml`** with pinned versions

```
# .env.example (committed to git)
ANTHROPIC_API_KEY=your-key-here
SEMANTIC_SCHOLAR_API_KEY=your-key-here

# .env (in .gitignore, never committed)
ANTHROPIC_API_KEY=sk-ant-actual-key
SEMANTIC_SCHOLAR_API_KEY=actual-key
```

### 3. Testing
You have zero tests right now. You don't need 100% coverage, but a few critical tests prevent regressions:

```python
# tests/test_enrichment.py
def test_doi_extraction_from_nature_url():
    url = "https://www.nature.com/articles/s41560-019-0356-8"
    doi = extract_doi_from_url(url)
    assert doi == "10.1038/s41560-019-0356-8"

def test_doi_extraction_from_iop_url():
    url = "https://iopscience.iop.org/article/10.1149/1945-7111/abae37"
    doi = extract_doi_from_url(url)
    assert doi == "10.1149/1945-7111/abae37"

def test_duplicate_detection_normalized_titles():
    title1 = "A decade of insights: Delving into calendar aging..."
    title2 = "A Decade of Insights: Delving Into Calendar Aging..."
    assert is_duplicate(title1, title2) == True
```

Run with: `pytest tests/`

Tell Claude Code:
```
Create a tests/ folder with basic tests for DOI extraction, duplicate detection, and metadata enrichment. Use pytest. Cover the cases we've been debugging — these are the functions that keep breaking.
```

### 4. Logging (Replace Print Statements)
You have debug print statements scattered everywhere. Replace with proper logging:

```python
import logging
logger = logging.getLogger(__name__)

# Instead of: print(f"[DEBUG] DOI extraction failed for {url}")
logger.debug(f"DOI extraction failed for {url}")

# Instead of: print(f"[ERROR] CrossRef timeout")
logger.error(f"CrossRef timeout for DOI {doi}")
```

Benefits: you can turn debug messages on/off without editing code, log to files, and filter by severity.

### 5. Type Hints
Makes Claude Code's suggestions much better and catches bugs earlier:

```python
# Instead of:
def enrich_paper(paper_id, force=False):

# Do:
def enrich_paper(paper_id: str, force: bool = False) -> dict:
```

### 6. Error Handling Strategy
Decide on a consistent approach instead of ad hoc try/except:

- **API calls**: Retry 3 times with exponential backoff, then fail gracefully
- **File I/O**: Check if file exists before reading, create directories if missing
- **User input**: Validate before processing (is this a valid DOI? Is this URL reachable?)
- **Never swallow exceptions silently** — at minimum, log them

### 7. Database Migrations
When you move to PostgreSQL, use Alembic for schema migrations. This lets you change your database schema without losing data:

```bash
alembic revision --autogenerate -m "add notes field to papers table"
alembic upgrade head
```

### 8. Documentation
Your current docs are scattered across many markdown files. Consolidate:

- **README.md** — how to set up and run the project (for anyone, including future you)
- **ARCHITECTURE.md** — how the system works (data flow, key decisions)
- **CONTRIBUTING.md** — how to add features (conventions, where things live)
- **CHANGELOG.md** — what changed in each version

Delete the one-off debugging docs (DUPLICATE_DETECTION_ANALYSIS.md, LIBRARY_COUNT_FIX.md, etc.) — they served their purpose.

### 9. CI/CD (When You're Ready)
GitHub Actions can automatically:
- Run your tests on every push
- Check for linting errors
- Build and deploy the app

This is overkill right now but becomes important when you have multiple contributors or a production deployment.

---

## Priority Matrix

| Priority | Task | Impact | Effort | Dependency |
|----------|------|--------|--------|------------|
| **P0** | Fix duplicate detection | High | Low | Blocks imports |
| **P0** | Fix UI bugs (batch) | Medium | Low | None |
| **P0** | Big Notion import | High | Low | Duplicate detection |
| **P1** | Batch metadata enrichment | High | Low | Semantic Scholar key ✅ |
| **P1** | Extract remaining pages from monolith | Medium | Medium | None |
| **P1** | Add query filters (chemistry/topic/year) | High | Medium | None |
| **P1** | Add basic tests | Medium | Low | None |
| **P2** | Multi-paper synthesis | High | Medium | None |
| **P2** | Auto-summarize on ingest | Medium | Low | None |
| **P2** | Connect to dataset catalog | High | Medium | None |
| **P2** | Replace print statements with logging | Low | Low | None |
| **P3** | FastAPI backend | High | High | Stable lib/ modules |
| **P3** | PostgreSQL + pgvector migration | High | High | FastAPI |
| **P3** | React frontend | High | High | FastAPI |
| **P4** | Figure/image handling | Medium | High | None |
| **P4** | Citation graph | Medium | High | References extracted |
| **P4** | Automated ingestion (Slack, RSS) | Medium | High | Production deploy |
| **P4** | Domain-specific embeddings | Medium | High | 1,000+ papers |

---

## Recommended Session Plan

Each session should be 2–4 hours focused on one thing. Don't context-switch.

| Session | Focus | Deliverable |
|---------|-------|-------------|
| Next | Fix duplicate detection + big import | 1,500+ papers in library |
| +1 | Batch enrichment + query filters | Enriched metadata, filtered queries |
| +2 | Extract remaining monolith pages | All pages independent, delete monolith |
| +3 | Add tests + logging + cleanup | Stable codebase, no debug prints |
| +4 | Multi-paper synthesis + auto-summarize | Research-grade query features |
| +5 | Dataset catalog connection | Flywheel link established |
| +6 | FastAPI backend (scaffold) | API endpoints wrapping lib/ |
| +7 | FastAPI backend (complete) | Full API, tested |
| +8 | PostgreSQL migration | Metadata + vectors in Postgres |
| +9 | React frontend (scaffold) | Basic pages, routing, table |
| +10 | React frontend (complete) | Full feature parity with Streamlit |
| +11 | Deploy | Docker Compose, running on a VPS |

---

## Decision Log

Decisions already made that should be respected:

| Decision | Rationale |
|----------|-----------|
| Don't rebuild Zotero | Focus on RAG/AI capabilities, not reference management |
| Streamlit is temporary | Will move to React + FastAPI when backend is stable |
| ChromaDB for now | Fine up to 1,000 papers; migrate to pgvector with Postgres |
| metadata.json for now | Fine for single user; migrate to Postgres with React |
| Skip Streamlit UI polish | All UI code gets thrown away in React migration |
| Backend features carry over | Invest in lib/ modules, not Streamlit pages |
| Semantic Scholar API key | Approved, 1 req/sec, set via SEMANTIC_SCHOLAR_API_KEY env var |
| Local sentence-transformers | Free, good enough for now; upgrade to domain-specific later |
