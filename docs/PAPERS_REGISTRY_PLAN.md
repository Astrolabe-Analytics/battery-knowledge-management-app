# Papers Registry & Cross-System Integration Plan

**Created:** 2026-03-31  
**Author:** Sebastian (decision owner) + FullStack agent (design + review)  
**Status:** Approved — ready for implementation  
**Review rounds:** 3 (all Critical/Important findings resolved)  
**Final verdict:** PASS WITH ISSUES (4.0/5) — remaining items are operational details resolved during implementation

---

## 1. Strategic Context

Astrolabe operates three interconnected systems that share a common S3 datalake:

1. **Battery Knowledge Management App (BKM)** — owns ~2,000 battery research papers with RAG search, metadata enrichment, cross-references
2. **Data Visualization Tool** — owns 340 datasets, projects, and cells; serves the public catalog
3. **Dataset Contribution/Ingestion Tool** — processes new datasets through AI-enriched pipeline; links papers to datasets

These systems will eventually merge into a unified platform with an AI agent-based data scientist running on top of all datalake data. This plan establishes the **paper registry** as a first-class entity in the datalake, enabling cross-system integration while preserving clean ownership boundaries.

---

## 2. Management-Level Data Flow

### What Papers Are and What They're Used For

**Papers** are academic publications (journal articles, preprints, technical reports) focused on battery research. The library of ~2,000 papers covers battery chemistry, degradation, testing methods, and datasets. Each paper includes:
- **Bibliographic metadata:** title, authors, journal, DOI, abstract, publication year
- **AI-extracted classifications:** chemistries (LFP, NMC, etc.), topics (degradation, SOH), application (EV, grid storage)
- **Cross-references:** citations to other papers (74K references, 87.5% with DOIs)
- **Full-text chunks:** text extracted from PDFs, split into ~600-token chunks with vector embeddings for RAG search

Papers are used for:
1. **RAG-powered Q&A:** researchers ask questions like "What degrades LFP cells faster — calendar aging or cycling?" and get sourced answers
2. **Dataset-to-paper linking:** when ingesting a dataset, the system matches it to relevant papers to establish provenance and context
3. **Metadata enrichment:** paper abstracts + classifications provide chemistry, methodology, and institution context that improves dataset metadata quality

### Why Postgres Exists Alongside PDF Files

**Two-tier storage architecture:**

| Layer | What It Stores | Why |
|-------|---------------|-----|
| **PDFs (S3)** | Raw source documents. Immutable binary blobs. | Authoritative source text for pipeline re-runs and manual review |
| **PostgreSQL + pgvector** | Structured metadata, 74K+ text chunks with 384-dim vector embeddings, 74K cross-references, collections | Fast vector search (cosine similarity), faceted filtering (chemistry, year, journal), full-text search |

Embeddings can't be derived from PDFs on-the-fly (takes 10+ seconds per paper), so they're pre-computed and cached in Postgres.

### How Papers Flow Through The System

```
PDF imported (URL, DOI, or upload)
    ↓ Stage 1: PARSE — pymupdf4llm extracts markdown text
    ↓ Stage 2: CHUNK — split into 600-token pieces with page/section tracking
    ↓ Stage 3: METADATA — CrossRef + Semantic Scholar + Claude extract bibliographic data
    ↓ Stage 4: EMBED — sentence-transformers generates 384-dim vectors per chunk
    ↓
PostgreSQL: Paper row (metadata) + Chunk rows (text + embeddings)
    ↓
User searches → vector similarity → top chunks → Claude synthesizes answer
```

### How This Connects to the Data-Viz Tool and Contribution Tool

```
┌─────────────────────────────────────────────────────┐
│        BATTERY KNOWLEDGE MANAGEMENT APP              │
│                                                      │
│  PDFs (S3)           PostgreSQL + pgvector           │
│  ┌──────────┐        ┌──────────────────────┐        │
│  │ 2,018    │ parse  │ Papers (metadata)     │        │
│  │ research │───────▶│ Chunks (text+vectors) │        │
│  │ papers   │ embed  │ References (74K cites) │       │
│  └──────────┘        └──────────┬───────────┘        │
│   Raw source docs      Structured, searchable        │
│   (immutable)          (enriched by CrossRef,        │
│                         Semantic Scholar, Claude)     │
│                                 │                     │
│              ┌──────────────────┤                     │
│              │                  │                     │
│         RAG Search         API Endpoints              │
│     "What degrades LFP?"  GET /paper-library          │
│     ──▶ vector search     POST /search/papers (Tier2) │
│     ──▶ Claude answer     ──▶ 2,018 papers with       │
│                               full metadata            │
└──────────────┬──────────────────┬─────────────────────┘
               │                  │
               │            ┌─────▼──────────┐
               │            │  S3 Datalake   │
               │            │ _system/       │
               │            │  paper-library.json │  ← NEW (this plan)
               │            │  registry.json │  (340 datasets)
               │            │  cells.json    │  (256 cells)
               │            │  projects.json │
               │            └─────┬──────────┘
               │                  │
       ┌───────▼──────────────────▼──────────────────┐
       │    DATASET INGESTION / CONTRIBUTION TOOL     │
       │                                              │
       │  Tier 1: Load paper library catalog           │
       │    → DOI exact match                          │
       │    → Title fuzzy match (Levenshtein ≥ 0.90)   │
       │    → CrossRef fallback                        │
       │    → Feed paper abstract to Claude enrichment │
       │                                              │
       │  Tier 2: Semantic paper discovery (NEW)       │
       │    → POST /api/system/paper-library/search     │
       │    → "Find papers about LFP calendar aging"   │
       │    → Returns relevant papers by content, not  │
       │      just DOI/title match                     │
       │    → Enables matching datasets to papers that │
       │      study the same phenomena                 │
       │                                              │
       │  Output: linkedPapers[] on dataset manifests  │
       │    {"paperId": "doi:10.1038/...",              │
       │     "confidence": "high",                      │
       │     "matchType": "doi-matched"}                │
       └──────────────────────┬───────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  DATA-VIZ TOOL    │
                    │  Datasets catalog │
                    │  (browse, search, │
                    │   filter, analyze)│
                    │                    │
                    │  Future: browse    │
                    │  papers like       │
                    │  datasets          │
                    └────────────────────┘
```

---

## 3. Ownership Model

**One-sided ownership:** datasets reference papers; papers don't know about datasets.

| Link | Owner | Stored In | Never In |
|------|-------|-----------|----------|
| Dataset → Papers | Dataset manifest (`linkedPapers[]`) | data-viz S3 `datasets/{id}/manifest.json` | BKM Paper record |
| Paper → Metadata | Paper record | BKM Postgres `papers` table | data-viz manifest |
| Paper → PDF | Paper storage | S3 `papers/{filename}` | duplicated anywhere |

**Why:** Papers exist independently of Astrolabe's dataset catalog. A paper can be referenced by 0-N datasets. Updates to paper metadata (abstract, authors, topics) happen in one place (BKM Postgres). Datasets store only a reference (`paperId` + confidence).

---

## 4. S3 Structure

```
s3://astrolabe-datalake/
  _system/
    registry.json     ← datasets (340, exists)
    cells.json        ← cells (256, exists)
    projects.json     ← projects (exists)
    paper-library.json ← NEW paper registry (this plan — matches existing S3 key)

  papers/              ← PDFs (flat, by filename — existing structure)
    doi_10_1038_...pdf
    arxiv_2301.05555v2.pdf
    ...
  
  datasets/{id}/       ← per-dataset folder (existing)
    manifest.json      ← includes linkedPapers[] (backfill already complete, 87/87)
    config.json
    data/
    raw/
```

---

## 5. `_system/paper-library.json` Schema

```json
{
  "version": "1.0.0",
  "schemaVersion": "1.0.0",
  "lastUpdated": "2026-03-31T14:30:00Z",
  "source": "battery-knowledge-management-app",
  "stats": {
    "total": 2018,
    "withDoi": 1876,
    "withPdf": 1703,
    "embedded": 1734,
    "withAiSummary": 127,
    "embeddingModel": "all-MiniLM-L6-v2"
  },
  "papers": [
    {
      "paperId": "doi:10.1038/s41467-019-09792-9",
      "filename": "doi_10_1038_s41467-019-09792-9.pdf",
      "title": "Data-driven prediction of battery cycle life...",
      "doi": "10.1038/s41467-019-09792-9",
      "authors": [{"given": "Kristen", "family": "Severson"}],
      "year": 2019,
      "journal": "Nature Energy",
      "abstract": "Accurately predicting battery...",
      "chemistries": ["LFP"],
      "topics": ["degradation", "cycle-life"],
      "application": "ev",
      "paperType": "Experimental",
      "pdfStatus": "available",
      "ragReady": true,
      "provisional": false,
      "source": "library",
      "lastModified": "2026-03-20T10:00:00Z"
    }
  ]
}
```

**Schema notes:**
- `version` = data version (incremented on breaking changes to papers array shape)
- `schemaVersion` = format version (incremented on envelope changes — adding stats fields, etc.)
- `stats.embeddingModel` documents which model produced embeddings, so consumers verify compatibility
- Stats calculated at export time via SQL COUNT queries
- `abstract` is critical — used by contribution tool's Claude enrichment prompt (max 1500 chars)
- `ragReady` indicates whether the paper has pgvector embeddings (enables Tier 2 semantic discovery)

**Envelope compatibility contract:** The data-viz-tool's `process.mjs` already normalizes both envelope `{version, stats, papers:[]}` and flat `[{paperId,...}]` formats on read (`Array.isArray(fetched) ? fetched : fetched?.papers ?? []`). The Python exporter must use the key `papers` for the array inside the envelope. Do not rename this field — it is a silent contract between exporter and consumer.

**S3 key ownership:** `_system/paper-library.json` was previously written by `scripts/dataset-pipeline/export-paper-library.mjs` in the data-viz-tool (Node.js, reads from local `metadata.json`). Once this plan's Step 5 runs in production, the Python exporter (Postgres → S3) takes ownership. After that, `export-paper-library.mjs --source` is **deprecated for production use** — running it will silently overwrite the Postgres-sourced file with older local metadata. The Node.js exporter remains available for local dev/testing only.

---

## 6. paperId Derivation & Immutability

### Derivation Rules

1. If `paper.doi` present: `paperId = f"doi:{normalize(doi)}"`
2. Else: `paperId = f"title:{slugify(title)[:60]}-{year}"`
3. Collision guard: append `-a` through `-e`, then `key:{sha256[:20]}`
4. Max collision depth: 5 suffixes + SHA256 fallback. Log warning when SHA256 triggers.

### Immutability Contract

Once written to `papers.paper_id` in Postgres, `paperId` is **immutable** — even if DOI is later discovered:
- `papers.doi` column is updated (for lookup)
- `papers.paper_id` stays as original `title:slug` value

**Why:** Datasets store `linkedPapers[].paperId`. If paperId changes, all referencing dataset manifests break. Stability > elegance.

**Lookup path:** Consumer queries by DOI use `papers.doi` column directly. The `paperId` is a stable reference key, not a lookup key.

---

## 7. Cross-System RAG Integration (Tier 2)

### The Problem

The contribution tool currently can only match papers by:
- **DOI exact match** — requires dataset to have a DOI
- **Title fuzzy match** (Levenshtein ≥ 0.90) — requires nearly identical title
- **CrossRef fallback** — fetches by DOI, rate-limited (1 req/s)

This misses papers that study the **same phenomena** as the dataset but don't share a DOI or title. Example: a dataset of "LFP calendar aging under 45°C" should be linked to papers about LFP calendar aging mechanisms, even if no DOI match exists.

### The Solution: `POST /api/system/paper-library/search`

A new endpoint on the BKM app that the contribution tool's enrichment agent can call:

```python
class PaperDiscoveryRequest(BaseModel):
    query: str              # Dataset description or enrichment context
    chemistries: list[str] = []  # Optional filter
    top_k: int = 10

class PaperDiscoveryResponse(BaseModel):
    papers: list[dict]      # [{paperId, doi, title, abstract, relevanceScore, matchReason}]
```

**How it works:**
1. Embeds the query using the same sentence-transformer model (all-MiniLM-L6-v2)
2. Runs pgvector cosine similarity search against paper chunks
3. Groups by paper (deduplicates chunks from same paper)
4. Returns paper-level results with relevance scores
5. Enrichment agent includes discovered papers as additional context for Claude synthesis

**Integration flow (contribution tool Stage 3.5):**
```
Existing:   paperRefs → linkPapers(refs, library)   → DOI/title match
                                                       ↓
New:        datasetDescription → POST /api/system/paper-library/search → semantic match
                                                       ↓
Merged:     linkedPapers[] = DOI matches + semantic matches (deduplicated)
            Claude enrichment receives ALL matched paper abstracts
```

**Why this matters:** A dataset about "NCR18650B cells aged at 45°C" gets matched not just to its source paper (DOI match), but also to papers studying similar cell aging under similar conditions. Claude then uses those additional paper abstracts to produce more accurate chemistry classifications, better descriptions with domain context, and richer metadata.

### What This Means for the Contribution Tool

The contribution tool's `record-synthesizer.mjs` already accepts paper evidence in its Claude prompt:

```javascript
// Current: passes ONE paper (if DOI matched)
if (paper.abstract) pLines.push(`Abstract: ${paper.abstract.substring(0, 1500)}`);

// Enhanced: passes MULTIPLE papers (DOI + semantic matches)
if (papers.length > 0) {
  for (const p of papers.slice(0, 3)) {
    pLines.push(`--- Related Paper (${p.matchType}) ---`);
    pLines.push(`Title: ${p.title}`);
    pLines.push(`Abstract: ${p.abstract?.substring(0, 500)}`);
    pLines.push(`Chemistries: ${p.chemistries?.join(', ')}`);
  }
}
```

Claude with 3 relevant paper abstracts instead of 1 (or 0) produces dramatically better:
- Chemistry classifications (papers name exact chemistry explicitly)
- Test condition descriptions (papers describe methodology)
- Application categorization (papers state the use case)

### Integration Tiers (Decision)

| Tier | What | When | Effort |
|------|------|------|--------|
| **Tier 1** | Paper library as reference catalog — DOI/title matching + abstracts | This plan (Steps 1-6) | Medium |
| **Tier 2** | Semantic paper discovery endpoint — find papers by content similarity | This plan (Step 4b) | Low (reuses pgvector) |
| **Tier 3** | Full RAG-grounded enrichment — ask BKM questions, get sourced answers | Future (requires BKM deployed + contribution tool mature) | High |

**Tier 3 is deferred** because it adds runtime dependency, latency, and complexity. Tiers 1+2 get 90% of the benefit.

---

## 8. Implementation Steps

### Step 1: Fix S3 bucket defaults

| File | Change |
|------|--------|
| `lib/s3_storage.py` line 40 | Default `astrolabe-knowledge-pdfs` → `astrolabe-datalake` |
| `deployment/ecs-task-definition.json` | `PAPERS_S3_BUCKET` value → `astrolabe-datalake` |

**Environment:** All (affects all deployment targets)  
**Risk:** Low — .env already has correct value; this fixes the fallback default  
**Verify:** `grep -n "astrolabe-knowledge-pdfs" lib/s3_storage.py deployment/ecs-task-definition.json` returns nothing

### Step 2: Database migration — add paper_id column

```sql
ALTER TABLE papers ADD COLUMN paper_id VARCHAR(255);
CREATE UNIQUE INDEX ix_papers_paper_id ON papers (paper_id) WHERE paper_id IS NOT NULL;
```

Also add `paper_id` to `lib/models.py` Paper class.

**Environment:** Local (Docker Compose Postgres), then staging RDS, then production RDS  
**Risk:** Low — additive column, no data migration  
**Verify:** `docker compose exec api python -c "from lib.models import Paper; print(Paper.paper_id)"`

**Deployment sequencing:** After applying this migration (or on a fresh DB), run `--assign-only` before `GET /api/system/paper-library` is called by any consumer. All existing papers will have `paper_id = NULL` until assignment runs. The endpoint returns `paperId: ""` for unassigned papers, which will break consumers that validate non-empty paperIds.

```bash
# Run immediately after migration / first deploy:
docker compose exec api python scripts/export_paper_registry.py --assign-only
```

### Step 3: Create `scripts/export_paper_registry.py`

Responsibilities:
- Read all non-deleted papers from Postgres
- Assign `paper_id` to any paper with NULL `paper_id` (backfill on first run)
- Write assigned `paper_id` values back to Postgres (single transaction, snapshot isolation)
- Serialize to papers.json format
- Validate before upload:
  1. All paperId non-null
  2. No duplicate paperId values
  3. Sample 10 records have expected fields
  4. Count matches DB (within transaction)
- Upload to S3 atomically (write `.tmp` key, validate, copy to `_system/paper-library.json`, delete `.tmp`)
- Log: start/end timestamps, papers processed, errors, S3 upload result

Flags:
- `--dry-run` (default): validate and show what would be exported
- `--write`: actually upload to S3
- `--assign-only`: just assign paper_ids to Postgres without S3 export

**Environment:** Run inside Docker (`docker compose exec api python scripts/export_paper_registry.py`)  
**Risk:** Medium — writes to Postgres and S3. Mitigated by `--dry-run` default + validation.

### Step 4a: Add `GET /api/system/paper-library` route

Added to `api/routes/papers.py`. Reads directly from Postgres. Returns array format matching what `paper-linker.mjs` expects:

```json
[
  {"paperId": "doi:10.1038/...", "doi": "...", "title": "...", "abstract": "...", ...}
]
```

Serves fresh data (no stale S3 cache risk). No auth (consistent with all existing endpoints — ALB perimeter auth handles access control per deployment plan).

**Environment:** All  
**Verify:** `curl -s http://localhost:8003/api/system/paper-library | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d), 'papers')"`

### Step 4b: Add `POST /api/system/paper-library/search` endpoint (Tier 2)

Semantic paper discovery. Reuses existing pgvector search infrastructure from `lib/db_operations.py`.

Only papers with `ragReady: true` (pgvector embeddings present) are eligible for semantic search results.

**`matchReason` field:** Return a structured string like `"semantic:cosine-0.87"` or `"semantic:chunk-similarity"` rather than free text. The pipeline needs to programmatically distinguish this from DOI or title matches when building the evidence chain.

**Evidence labeling (consumer's responsibility, not BKM's):** BKM returns papers with `relevanceScore` and `matchReason`. The consumer (data-viz-tool `process.mjs`) stamps `source: "semantic_discovery"` on these and applies a 0.50 confidence ceiling per the pipeline's established external-evidence doctrine — the same cap that applies to BatteryArchive, Robert's CSV, and all non-authoritative sources. BKM does not enforce this cap; it just returns ranked results. Do not add a `source` field to the BKM response payload.

**`BKM_API_URL` placement:** This env var belongs in the **data-viz-tool / contribution-tool environment**, not BKM's. BKM doesn't consume it. BKM's job here is: (a) endpoint works, (b) document the URL pattern for the consumer team. The actual wiring (`BKM_API_URL` read in `process.mjs`, `POST /api/system/paper-library/search` call in Stage 3.5) is data-viz-tool work, outside this plan's scope.

**Tier 1 vs Tier 2 runtime dependency:** Tier 1 (paper library catalog) flows through S3 — `process.mjs` reads `_system/paper-library.json` via the data-viz-tool API. It does not call BKM directly at runtime. Tier 2 is the **first** time the pipeline calls BKM directly. If `BKM_API_URL` is unset or BKM is unreachable, Tier 2 is skipped — Tier 1 is unaffected.

**Environment:** All
**Verify:** `curl -s -X POST http://localhost:8003/api/system/paper-library/search -H 'Content-Type: application/json' -d '{"query": "LFP calendar aging", "top_k": 5}' | python3 -m json.tool`

### Step 5: Run export script

```bash
# Dry run
docker compose exec api python scripts/export_paper_registry.py --dry-run

# Write to S3 (production: use astrolabe-ro profile for read verification)
docker compose exec api python scripts/export_paper_registry.py --write
```

**Export schedule (v1):** Manual — run after bulk imports or weekly. Future: daily cron via ECS scheduled task.

### Step 6: Confirm `linkedPapers[]` backfill status (already complete)

The migration from `associatedPapers[]` (URL stubs) → `linkedPapers[]` (proper `paperId` references) ran previously via `scripts/migrations/backfill-linked-papers.js` in the data-viz-tool. 87/87 datasets were written; the script is idempotent.

**Verification only — no write needed:**
```bash
# Confirm datasets have linkedPapers (run on host with astrolabe-ro profile)
AWS_PROFILE=astrolabe-ro node scripts/migrations/backfill-linked-papers.js
# (dry-run default — should show 0 candidates remaining)
```

**What's not done yet — full cross-library matching:** `backfill-linked-papers.js` normalizes links that were already in `associatedPapers[]`. It does not look up new links by querying the full 2,018-paper library. Datasets that had no `associatedPapers` entry don't gain new paper links from this script. Full cross-library discovery (using the new `GET /api/system/paper-library` endpoint to match dataset sources against all papers) is a separate piece of work, not in scope for this plan. New links are created going forward by the contribution pipeline's `paper-linker.mjs` on each ingest run.

---

## 9. Development → Staging → Production Flow

### Local Development (localhost + Docker Compose)

```
┌─────────────────────────────────────────┐
│  docker compose up -d                   │
│                                         │
│  API:       localhost:8003              │
│  Frontend:  localhost:5173 (Vite HMR)   │
│  Postgres:  localhost:5432              │
│  LocalStack: localhost:4566 (optional)  │
│                                         │
│  PAPERS_STORAGE=         (local mode)   │
│  PDFs in papers/ directory              │
│  DB: postgres/postgres/astrolabe        │
└─────────────────────────────────────────┘
```

**Steps 1-4 are developed and tested here.**

To test S3 integration locally:
```bash
docker compose --profile s3 up -d      # starts LocalStack
./scripts/setup_localstack.sh           # creates bucket
# Set in .env:
PAPERS_STORAGE=s3
AWS_ENDPOINT=http://localhost:4566

docker compose restart api

# Test export to LocalStack S3
docker compose exec api python scripts/export_paper_registry.py --write
aws --endpoint-url=http://localhost:4566 s3 cp s3://astrolabe-datalake/_system/paper-library.json - | python3 -m json.tool | head -20
```

### Staging (ECS + RDS + S3)

```
┌─────────────────────────────────────────┐
│  ECS Fargate (staging cluster)          │
│  ALB: staging-knowledge.astrolabe-...   │
│                                         │
│  PAPERS_STORAGE=s3                      │
│  PAPERS_S3_BUCKET=astrolabe-datalake    │
│  DATABASE_URL=rds-staging-endpoint      │
│                                         │
│  Same Docker image as production        │
│  Same S3 bucket (production datalake)   │
│  Separate RDS instance (staging DB)     │
└─────────────────────────────────────────┘
```

**Steps 5-6 first run on staging.**

Staging deployment:
```bash
# Build + push image
docker build --target api -t knowledge-app:staging .
# Push to ECR (Hardik handles IAM/ECR setup)

# Run DB migration on staging RDS
# Run export script against staging
# Verify API endpoint returns papers
# Verify data-viz-tool can fetch paper library from staging
```

### Production (ECS + RDS + S3)

```
┌─────────────────────────────────────────┐
│  ECS Fargate (production cluster)       │
│  ALB: knowledge.astrolabe-analytics.com │
│                                         │
│  PAPERS_STORAGE=s3                      │
│  PAPERS_S3_BUCKET=astrolabe-datalake    │
│  DATABASE_URL=rds-production-endpoint   │
│  Secrets via AWS Secrets Manager        │
│                                         │
│  ALB auth: Cognito OIDC (Phase 2)      │
└─────────────────────────────────────────┘
```

Production deployment:
```bash
# After staging validation passes
# Tag staging image as production
# Update ECS service
# Run DB migration on production RDS
# Run export script with --write (writes _system/paper-library.json to production S3)
# Verify data-viz-tool production can consume paper library
```

---

## 10. Review Checkpoints

Independent sub-agent reviews at key milestones using the project's review protocol (auto-fix Critical/Important, max 2 rounds per checkpoint).

### Checkpoint 1: After Steps 1-2 (Infrastructure)

**Reviewer focus:** Database schema correctness, S3 bucket configuration, model changes  
**Specialist profile:** Database migration + cloud infrastructure specialist  
**Pass criteria:** No regressions in existing functionality, paper_id column correct, bucket defaults fixed

### Checkpoint 2: After Steps 3-4 (Export + API)

**Reviewer focus:** Export script correctness (paperId derivation, validation, atomic S3 write), API endpoint format compatibility with data-viz consumers, Tier 2 semantic search quality  
**Specialist profile:** API design + data pipeline specialist  
**Pass criteria:** Export produces valid papers.json, API returns format paper-linker.mjs expects, semantic search returns relevant results

### Checkpoint 3: After Steps 5-6 (Integration)

**Reviewer focus:** Cross-system integration, paper link quality, dataset manifest updates  
**Specialist profile:** Cross-system integration specialist  
**Pass criteria:** paper-library endpoint consumable by data-viz pipeline, backfill upgrades associatedPapers to linkedPapers, no broken dataset manifests

### Checkpoint 4: Pre-deployment (Full system)

**Reviewer focus:** Security (endpoint exposure, input validation), deployment configuration (ECS task def, secrets), operational readiness  
**Specialist profile:** Security + deployment specialist  
**Pass criteria:** No exposed secrets, all env vars documented, health check works, structured logging for CloudWatch

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Export script crash leaves corrupt S3 | Low | High | Atomic write (tmp + copy pattern), JSON validation before upload |
| paperId collision exhausts suffix space | Very Low | Medium | SHA256 fallback after 5 suffixes, log warning, track in stats |
| Paper library too large for API response | Low (2K papers now) | Medium | Add ETag/If-None-Match headers; pagination at 50K+ |
| Semantic discovery latency | Low | Low | pgvector search typically <200ms; 5s timeout in contribution tool |
| Contribution tool unavailable when BKM is down | Medium | Medium | Tier 1 (catalog) works from S3 snapshot; Tier 2 (semantic) degrades gracefully |
| paperId → DOI mismatch after enrichment | Medium | Low | Immutability contract: paperId never changes; DOI lookup uses separate column |

---

## 12. What This Unlocks

### Immediate (this plan)
- Knowledge app PDF storage uses correct S3 bucket
- Paper registry published to datalake (`_system/paper-library.json`)
- Ingestion tool can match papers by DOI + title + semantic similarity
- 87 existing dataset↔paper links already upgraded (backfill ran previously, idempotent)
- Claude enrichment gets paper abstracts for better metadata synthesis

### Near-term (after deployment)
- Data-viz tool can browse papers alongside datasets (registry exists)
- Contribution tool uses Tier 2 semantic search for richer paper matching
- Paper library endpoint available for any future consumer

### Long-term (unified platform)
- Papers become browsable entities in data-viz (like datasets, cells, projects)
- AI data scientist agent queries BKM RAG for deep paper analysis (Tier 3)
- Paper↔dataset linkages enable citation graph and provenance tracking
- One-sided ownership model survives platform merge — papers registry becomes a view, not a separate system

---

## 13. Files Changed / Created

| File | Action | Step |
|------|--------|------|
| `lib/s3_storage.py` | Edit: bucket default | 1 |
| `deployment/ecs-task-definition.json` | Edit: bucket value | 1 |
| `lib/models.py` | Edit: add `paper_id` column | 2 |
| `scripts/export_paper_registry.py` | **Create** | 3 |
| `api/routes/system.py` | **Create**: paper-library + search/papers endpoints | 4 |
| `api/main.py` | Edit: mount system router | 4 |
| `lib/db_operations.py` | Edit: add paper library export + semantic paper search functions | 4 |

---

## Appendix A: Verification Commands

```bash
# After Step 1 — bucket defaults fixed
rg "astrolabe-knowledge-pdfs" lib/ deployment/  # should return nothing

# After Step 2 — paper_id column exists
docker compose exec api python -c "
from lib.db import get_session
from lib.models import Paper
with get_session() as s:
    p = s.query(Paper).first()
    print(f'paper_id column exists: {hasattr(p, \"paper_id\")}')"

# After Step 3 — export script works
docker compose exec api python scripts/export_paper_registry.py --dry-run

# After Step 4a — paper library endpoint works
curl -s http://localhost:8003/api/system/paper-library | python3 -c "
import json, sys
papers = json.load(sys.stdin)
print(f'{len(papers)} papers')
assert all(p.get('paperId') for p in papers), 'NULL paperId'
print('PASS')"

# After Step 4b — semantic search works
curl -s -X POST http://localhost:8003/api/system/paper-library/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "LFP calendar aging under high temperature", "top_k": 5}' | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d[\"papers\"])} results'); print('PASS')"

# After Step 5 — S3 export valid
aws s3 cp s3://astrolabe-datalake/_system/paper-library.json - --profile astrolabe-ro | python3 -c "
import json, sys
d = json.load(sys.stdin)
# Handle both envelope {papers:[]} and flat [] formats
papers = d['papers'] if isinstance(d, dict) else d
stats = d.get('stats', {}) if isinstance(d, dict) else {}
print(f'Papers: {len(papers)}, DOIs: {stats.get(\"withDoi\", \"unknown\")}')
ids = [p['paperId'] for p in papers]
assert len(set(ids)) == len(ids), 'Duplicate paperId'
print('PASS')"

# paperId stability (run export twice, compare)
docker compose exec api python scripts/export_paper_registry.py --dry-run > /tmp/e1.json
docker compose exec api python scripts/export_paper_registry.py --dry-run > /tmp/e2.json
diff /tmp/e1.json /tmp/e2.json && echo "STABLE" || echo "UNSTABLE"

# After Step 6 — confirm backfill already complete (dry-run should show 0 remaining)
# Run in data-viz-tool repo, on host (not Docker)
node scripts/migrations/backfill-linked-papers.js
# Expected: "0 datasets need updating" or equivalent idempotent output
```
