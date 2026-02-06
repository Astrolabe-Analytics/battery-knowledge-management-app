# Editable DOI & Auto-Metadata Guide

## Overview

You can now edit DOI values directly in the library and automatically populate metadata from CrossRef.

## Features Implemented

### 1. Editable DOI in Table ✓

**How to use:**
1. Double-click on any DOI cell in the table
2. Type or paste a new DOI (format: `10.xxxx/xxxxx`)
3. Press Enter or click outside the cell

**What happens:**
- System queries CrossRef API with the new DOI
- If found, automatically updates:
  - Title
  - Authors (formatted as "Last, First")
  - Year
  - Journal
- Shows success notification: "✅ Metadata updated from CrossRef!"
- Displays updated metadata in a popup
- Saves changes to `data/metadata.json`
- Updates all chunks in ChromaDB

### 2. Manual Refresh in Detail View ✓

**How to use:**
1. Click on any paper to open detail view
2. Expand the "🔄 Update DOI & Metadata" section
3. Options:
   - **Edit DOI:** Modify the DOI in the text field
   - **🔄 Refresh from CrossRef:** Query CrossRef with current/edited DOI
   - **💾 Save DOI Only:** Save DOI without querying CrossRef

**Use cases:**
- **Add missing DOI:** Edit blank DOI field and click "Refresh from CrossRef"
- **Fix wrong DOI:** Replace incorrect DOI and click "Refresh from CrossRef"
- **Re-fetch metadata:** Click "Refresh from CrossRef" to overwrite current metadata
- **Save DOI only:** Save DOI without changing other metadata (useful if CrossRef data is incomplete)

### 3. Notifications ✓

**Toast notifications:**
- ✅ "Metadata updated from CrossRef!" - Success
- ⚠️ "DOI saved, but no metadata found in CrossRef" - DOI saved but no CrossRef data
- ✅ "DOI saved!" - DOI updated without metadata refresh

**Detailed feedback:**
- Shows updated title, authors, year, journal in popup
- Warnings if DOI not found or invalid

### 4. Persistence ✓

**All changes are saved to:**
1. **metadata.json** - Paper-level metadata store
2. **ChromaDB** - All chunks for that paper updated with new metadata

**Survives:**
- App restarts ✓
- Page refreshes ✓
- Streamlit reruns ✓

## Examples

### Example 1: Add DOI to Paper Without One

**Before:**
| Title | Authors | Year | Journal | DOI |
|-------|---------|------|---------|-----|
| History-Agnostic Battery... | Unknown | Unknown | Unknown | — |

**Steps:**
1. Double-click on "—" in DOI column
2. Paste DOI: `10.xxxx/xxxxx`
3. Press Enter

**After:**
| Title | Authors | Year | Journal | DOI |
|-------|---------|------|---------|-----|
| Data-driven prediction... | Smith, J.; Jones, A. | 2023 | Nature Energy | 10.xxxx/xxxxx |

All metadata automatically populated from CrossRef!

### Example 2: Fix Incorrect Year

**Before:**
- Paper has wrong year (2026 instead of 2024)
- DOI is correct

**Steps:**
1. Click paper to open detail view
2. Expand "🔄 Update DOI & Metadata"
3. Click "🔄 Refresh from CrossRef"
4. System re-fetches canonical data from CrossRef
5. Year updated to correct value (2024)

### Example 3: Update DOI Only (No Metadata Change)

**Use case:** You want to add/fix DOI but keep existing metadata

**Steps:**
1. Open detail view
2. Expand "🔄 Update DOI & Metadata"
3. Edit DOI field
4. Click "💾 Save DOI Only"
5. DOI saved without changing title, authors, etc.

## DOI Format

**Valid formats:**
- `10.1234/example` ✓
- `10.1149/1945-7111/abae37` ✓
- `10.1016/j.est.2026.120653` ✓

**Invalid formats:**
- `https://doi.org/10.1234/example` ✗ (include only the DOI part)
- `DOI: 10.1234/example` ✗ (no prefix)
- `doi:10.1234/example` ✗ (no prefix)

Just paste the DOI itself: `10.xxxx/xxxxx`

## CrossRef API

**What it provides:**
- Canonical bibliographic metadata
- Official title (not extracted from PDF)
- Properly formatted authors
- Publication year
- Journal name (full, not abbreviated)

**Limitations:**
- Not all papers have DOIs (especially older papers, preprints, technical reports)
- Some DOIs may not be in CrossRef database
- Rate limited to ~50 requests/minute (shouldn't be an issue for normal use)

## Workflow Recommendations

### When Adding New Papers

1. Add PDF to `papers/` directory
2. Run ingestion pipeline: `python scripts/ingest_pipeline.py --all --new-only`
3. Check library view - some papers may have DOI auto-extracted, others won't
4. For papers without DOI:
   - Look up DOI on publisher website or Google Scholar
   - Double-click DOI column in table
   - Paste DOI
   - Metadata automatically populated

### When Fixing Metadata

**Option A: Edit DOI in table (fastest)**
- Double-click DOI cell
- Enter correct DOI
- Auto-updates metadata

**Option B: Use detail view (more control)**
- Open paper detail view
- Expand DOI/Metadata section
- Edit DOI or click refresh
- Choose to update metadata or save DOI only

### Bulk Updates

Currently one-at-a-time in the UI. For bulk DOI updates, consider:
1. Editing `data/metadata.json` directly
2. Running metadata extraction with `--force`: `python scripts/ingest_pipeline.py --stage metadata --force`
3. Re-embedding: `python scripts/ingest_pipeline.py --stage embed --force`

## Technical Details

### Files Modified
- `app.py` - Added editable DOI column, CrossRef integration, UI controls
- `data/metadata.json` - Stores paper metadata including DOI
- ChromaDB (`data/chroma_db/`) - All chunks updated with new metadata

### Data Flow

```
User edits DOI
    ↓
Query CrossRef API
    ↓
Receive canonical metadata
    ↓
Update metadata.json
    ↓
Update ChromaDB (all chunks for paper)
    ↓
Show notification & refresh UI
```

### API Calls

**CrossRef API:**
- Endpoint: `https://api.crossref.org/works/{DOI}`
- Timeout: 10 seconds
- User-Agent: `BatteryPaperLibrary/1.0`
- No authentication required
- Free and unlimited (within reasonable rate limits)

## Troubleshooting

### "No metadata found in CrossRef"
- DOI may be invalid or not in CrossRef database
- Try searching publisher website for correct DOI
- Can still save DOI manually with "Save DOI Only"

### DOI field not editable
- Make sure you're double-clicking the cell (not single-click)
- Cell should show cursor when editable
- AG Grid must be fully loaded

### Changes not persisting
- Check that `data/metadata.json` exists and is writable
- Check Streamlit console for errors
- Verify ChromaDB is accessible

### CrossRef query slow
- Normal - can take 2-5 seconds per query
- Spinner shows while querying
- Consider doing bulk updates offline if many papers need updating

## Future Enhancements

- [ ] Bulk DOI editing (select multiple papers)
- [ ] DOI validation (check if DOI is valid format)
- [ ] Undo/redo functionality
- [ ] Metadata diff view (show what changed)
- [ ] Alternative sources (arXiv, PubMed, Google Scholar)
- [ ] Auto-suggest DOI based on title/authors
- [ ] Import from BibTeX/RIS files

## Best Practices

1. **Always use CrossRef when possible** - Most reliable metadata source
2. **Save DOI only when**:
   - CrossRef data is incomplete or wrong
   - You want to keep manually curated metadata
   - Paper not in CrossRef but you have DOI from publisher
3. **Verify metadata after auto-update** - Check that title, authors look correct
4. **Keep backups** - Copy `data/metadata.json` before bulk updates

## Conclusion

The editable DOI feature makes maintaining the paper library much easier. Instead of re-ingesting or manually editing files, you can now:
- Add DOIs directly in the UI
- Automatically populate metadata from CrossRef
- Fix errors without touching the command line
- Keep metadata consistent and accurate

All changes persist across sessions and are reflected in both the table view and search/query results.
