# Pipeline Usage Guide

Quick reference for using the PostgreSQL-native ingestion pipeline and maintenance scripts.

## Ingestion Pipeline

All ingestion goes through `scripts/ingest_pipeline_pg.py`, which writes directly to PostgreSQL + pgvector.

### Stages

| Stage | What it does | Input | Output |
|-------|-------------|-------|--------|
| 1 `parse` | PDF → Markdown via opendataloader-pdf | `papers/*.pdf` | `raw_text/*.md` |
| 2 `chunk` | Markdown → overlapping text chunks | `raw_text/*.md` | `data/chunks/*.json` |
| 3 `metadata` | Extract metadata via Claude → PostgreSQL | `raw_text/*.md` | `papers` table |
| 4 `embed` | Generate embeddings → pgvector | chunks + papers | `chunks` table |

### Basic Commands

```bash
# Process new papers (all 4 stages, skip already-processed)
python scripts/ingest_pipeline_pg.py --all --new-only

# Run a single stage
python scripts/ingest_pipeline_pg.py --stage parse
python scripts/ingest_pipeline_pg.py --stage chunk
python scripts/ingest_pipeline_pg.py --stage metadata --new-only
python scripts/ingest_pipeline_pg.py --stage embed

# Force re-process everything
python scripts/ingest_pipeline_pg.py --all --force
```

### Common Workflows

**Adding new papers:**
```bash
cp /path/to/new_paper.pdf papers/
python scripts/ingest_pipeline_pg.py --all --new-only
```

**Re-extracting metadata for all papers:**
```bash
python scripts/ingest_pipeline_pg.py --stage metadata --force
python scripts/ingest_pipeline_pg.py --stage embed --force
```

**Complete re-ingestion:**
```bash
python scripts/ingest_pipeline_pg.py --all --force
```

### Flags

| Flag | Effect |
|------|--------|
| `--all` | Run all 4 stages sequentially |
| `--stage <name>` | Run one stage: `parse`, `chunk`, `metadata`, `embed` |
| `--new-only` | Skip files already in pipeline state |
| `--force` | Re-process all files (ignore pipeline state) |

## Enrichment

```bash
# Bulk-enrich incomplete papers via CrossRef + Semantic Scholar
python scripts/enrich_pg_bulk.py

# Backfill DOIs for paper references
python scripts/backfill_ref_dois.py
```

## AI Summaries

```bash
# Generate AI summaries for papers that have PDF chunks
python scripts/generate_summaries_pg.py
```

## Maintenance Utilities

```bash
# Quick status check
python scripts/_check_status.py

# Fix ISSN-as-DOI errors
python scripts/_fix_bad_dois.py

# Fix MDPI URL-as-DOI errors
python scripts/_fix_mdpi_dois.py

# Analyze incomplete papers
python scripts/_analyze_incomplete.py

# Paper statistics
python scripts/_tally.py
```

## Database Migrations (Alembic)

Schema changes are managed via Alembic:

```bash
# After changing lib/models.py, generate a migration:
alembic revision --autogenerate -m "describe the change"

# Apply pending migrations:
alembic upgrade head

# Check current migration state:
alembic current
```

## Pipeline State

The pipeline tracks which papers have completed each stage in `data/pipeline_state.json`.
To force re-processing of specific papers, remove their filenames from the relevant arrays.

## File Locations

| Path | Purpose | Created By |
|------|---------|------------|
| `papers/` | Input PDFs | User |
| `raw_text/` | Parsed markdown | Stage 1 |
| `data/chunks/` | Chunked JSON (intermediate) | Stage 2 |
| `data/pipeline_state.json` | Stage completion tracking | All stages |
| PostgreSQL `papers` table | Paper metadata | Stage 3 / enrichment |
| PostgreSQL `chunks` table | Text + embeddings (pgvector) | Stage 4 |

### What to Keep
- `scripts/ingest.py` - Keep as reference, but use `ingest_pipeline.py` going forward
- All functionality is preserved in the new pipeline

## Help

```bash
python scripts/ingest_pipeline.py --help
```

For issues or questions, see `PIPELINE_TESTING_SUMMARY.md` for detailed test results and performance metrics.
