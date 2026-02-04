# Pipeline Usage Guide

Quick reference for using the modular ingestion pipeline.

## Basic Commands

### Process Everything (New Papers Only)
```bash
python scripts/ingest_pipeline.py --all --new-only
```
**Use when:** Adding new papers to the library

### Run Individual Stages

#### Stage 1: Parse PDFs to Markdown
```bash
python scripts/ingest_pipeline.py --stage parse
```
**Duration:** ~12s per paper
**Input:** PDF files in `papers/`
**Output:** Markdown in `raw_text/`

#### Stage 2: Create Chunks from Markdown
```bash
python scripts/ingest_pipeline.py --stage chunk
```
**Duration:** <1s for all files
**Input:** Markdown in `raw_text/`
**Output:** JSON in `data/chunks/`

#### Stage 3: Extract Metadata
```bash
python scripts/ingest_pipeline.py --stage metadata
```
**Duration:** ~33s per paper (includes API calls)
**Input:** Markdown in `raw_text/`
**Output:** `data/metadata.json`

#### Stage 4: Generate Embeddings
```bash
python scripts/ingest_pipeline.py --stage embed
```
**Duration:** ~15s for all chunks
**Input:** Chunks + metadata
**Output:** ChromaDB in `data/chroma_db/`

## Useful Flags

### --new-only
Process only files not in pipeline state
```bash
python scripts/ingest_pipeline.py --stage metadata --new-only
```

### --force
Re-process all files (ignore pipeline state)
```bash
python scripts/ingest_pipeline.py --stage chunk --force
```

### --all
Run all 4 stages sequentially
```bash
python scripts/ingest_pipeline.py --all
```

## Common Workflows

### 1. Adding New Papers
```bash
# 1. Copy PDF to papers/ directory
cp /path/to/new_paper.pdf papers/

# 2. Run pipeline for new papers only
python scripts/ingest_pipeline.py --all --new-only

# 3. Start Streamlit app
streamlit run app.py
```

### 2. Fixing Metadata for One Paper
```bash
# 1. Delete the paper from pipeline state
# Edit data/pipeline_state.json and remove filename from "metadata" array

# 2. Re-extract metadata for that paper
python scripts/ingest_pipeline.py --stage metadata --new-only

# 3. Re-embed (uses updated metadata)
python scripts/ingest_pipeline.py --stage embed --force
```

### 3. Improving Metadata Extraction Prompt
```bash
# 1. Edit extract_paper_metadata() in scripts/ingest_pipeline.py
# Modify the Claude prompt (around line 200-250)

# 2. Re-extract metadata for all papers
python scripts/ingest_pipeline.py --stage metadata --force

# 3. Re-embed with new metadata
python scripts/ingest_pipeline.py --stage embed --force
```

### 4. Testing New Chunking Strategy
```bash
# 1. Edit create_chunks() in scripts/ingest_pipeline.py
# Modify chunk_size, chunk_overlap, etc.

# 2. Re-chunk all files
python scripts/ingest_pipeline.py --stage chunk --force

# 3. Re-embed with new chunks
python scripts/ingest_pipeline.py --stage embed --force
```

### 5. Complete Re-ingestion
```bash
# Force re-run all stages
python scripts/ingest_pipeline.py --all --force
```

### 6. Clean Start
```bash
# 1. Delete all intermediate files and state
rm -rf raw_text/ data/chunks/ data/metadata.json data/pipeline_state.json data/chroma_db/

# 2. Run full pipeline
python scripts/ingest_pipeline.py --all
```

## Pipeline State

The pipeline tracks which papers have completed each stage in `data/pipeline_state.json`:

```json
{
  "parsed": ["paper1.pdf", "paper2.pdf", ...],
  "chunked": ["paper1.pdf", "paper2.pdf", ...],
  "metadata": ["paper1.pdf", "paper2.pdf", ...],
  "embedded": ["paper1.pdf", "paper2.pdf", ...],
  "last_updated": "2026-02-04 14:04:10"
}
```

### Manually Edit State
To force re-processing of specific papers, remove their filenames from the relevant arrays.

## Troubleshooting

### "No markdown files found"
**Problem:** Stage 2/3/4 can't find input files
**Solution:** Run stage 1 first: `python scripts/ingest_pipeline.py --stage parse`

### "ANTHROPIC_API_KEY not found"
**Problem:** Stage 3 requires API key for metadata extraction
**Solution:** Set environment variable: `export ANTHROPIC_API_KEY=your-key-here`

### "Collection already exists"
**Problem:** ChromaDB has existing data
**Solution:** Normal behavior - stage 4 will add/update chunks

### Papers not appearing in Streamlit
**Problem:** Pipeline completed but papers not visible in UI
**Solution:**
1. Check database: `python -c "from lib import rag; print(len(rag.get_paper_library()))"`
2. Restart Streamlit: `streamlit run app.py`

### Metadata extraction failing
**Problem:** API errors during stage 3
**Solution:**
1. Check API key is valid
2. Wait 30 seconds between papers (rate limiting)
3. Use `--new-only` to skip successful papers

## Performance Tips

### Faster Iteration
- Use `--stage` instead of `--all` to run only changed stages
- Use `--new-only` to skip already-processed papers
- Keep intermediate files (raw_text, chunks) to avoid re-parsing

### Batch Processing
- Process large batches overnight using `--all`
- Monitor progress with `tqdm` progress bars
- Check `data/pipeline_state.json` to see completion status

## File Locations

| Directory/File | Purpose | Created By |
|----------------|---------|------------|
| `papers/` | Input PDFs | User |
| `raw_text/` | Parsed markdown | Stage 1 |
| `data/chunks/` | Chunked JSON | Stage 2 |
| `data/metadata.json` | Extracted metadata | Stage 3 |
| `data/chroma_db/` | Vector database | Stage 4 |
| `data/pipeline_state.json` | State tracking | All stages |

## Migration from Old Script

If you were using `scripts/ingest.py` before:

### Differences
- **Old:** Single monolithic script, all-or-nothing
- **New:** Modular pipeline, run stages independently

### Migration Steps
```bash
# 1. Backup old database
mv data/chroma_db data/chroma_db.backup

# 2. Run new pipeline
python scripts/ingest_pipeline.py --all

# 3. Verify results
python -c "from lib import rag; print(len(rag.get_paper_library()))"

# 4. Test in Streamlit
streamlit run app.py
```

### What to Keep
- `scripts/ingest.py` - Keep as reference, but use `ingest_pipeline.py` going forward
- All functionality is preserved in the new pipeline

## Help

```bash
python scripts/ingest_pipeline.py --help
```

For issues or questions, see `PIPELINE_TESTING_SUMMARY.md` for detailed test results and performance metrics.
