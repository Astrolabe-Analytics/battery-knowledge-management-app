# CSV/Excel Import Feature - User Guide

**Date:** 2026-02-05
**Status:** ✅ Complete and Ready

## Overview

Import papers in bulk from CSV or Excel files (e.g., Notion exports, Battery Datasets catalog, reference manager exports, custom paper lists). The feature automatically extracts DOIs from URLs, fetches metadata from CrossRef, searches for open access PDFs, and handles duplicate detection.

## Supported File Formats

### CSV Files (.csv)
- Notion database exports
- Reference manager exports (Zotero, Mendeley)
- Custom paper lists
- Any CSV with paper metadata

### Excel Files (.xlsx, .xls)
- Battery Datasets catalog (auto-detects "Battery_Datasets" sheet)
- Custom Excel spreadsheets
- Multi-sheet workbooks (uses first sheet or "Battery_Datasets" if present)

## Quick Start

1. Open the app → Go to **Import** tab
2. Scroll to **"📊 Import from CSV"** section
3. Click **"Upload CSV file"** and select your CSV
4. Review the preview of papers
5. Set **batch size** (start with 5-10 to test)
6. Click **"📥 Import Papers from CSV"**
7. Watch the progress as papers are imported
8. Review the summary (imported, skipped, failed counts)

## CSV Format

### Required Column

- **Title** - Paper title (required, papers without titles are skipped)

### Recommended Columns

- **URL** - DOI or paper URL (used to fetch full metadata)
- **Authors / Orgs** or **Authors** - Author names
- **Publication Year** or **Year** - Publication year
- **Journal** - Journal name
- **Tags** - Keywords/tags (comma-separated)
- **Abstract/Notes** or **Abstract** - Paper abstract
- **Citations** - Citation count

### Column Name Flexibility

The importer recognizes multiple column name variations:
- `Title` or `title`
- `URL` or `url`
- `Authors / Orgs` or `Authors` or `authors`
- `Publication Year` or `Year` or `year`
- `Journal` or `journal`
- `Abstract/Notes` or `Abstract` or `abstract`
- `Tags` or `tags`

## Notion Export Example

Your Notion export (`_all.csv`) with 1,634 papers is perfect! It has:
- ✅ Title column
- ✅ URL column (for DOI extraction)
- ✅ Authors / Orgs column
- ✅ Publication Year column
- ✅ Journal column
- ✅ Tags column
- ✅ Abstract/Notes column

**To import:**
1. Extract the CSV from the zip file first
2. Upload the `_all.csv` file
3. Start with batch size of 10 papers to test
4. If successful, import more batches

## Battery Datasets Excel Example

The Battery Datasets catalog Excel file is fully supported! Features:
- ✅ Auto-detects "Battery_Datasets" sheet
- ✅ Maps `paper_url` → URL (for DOI extraction)
- ✅ Maps `chemistry` → Tags (battery chemistry type)
- ✅ Maps `title` → Title
- ✅ Maps `authors` → Authors
- ✅ Maps `journal` → Journal
- ✅ Merges chemistry with existing tags

**Excel Column Mapping:**
```
Battery Datasets → Library Field
─────────────────────────────────
paper_url        → URL (DOI extraction)
title            → Title
chemistry        → Tags (merged)
authors          → Authors
journal          → Journal
tags             → Tags
```

**To import:**
1. Upload the Excel file (.xlsx or .xls)
2. System auto-detects "Battery_Datasets" sheet
3. Shows: "📊 Detected Battery Datasets catalog format"
4. Start with batch size of 10 papers to test
5. Chemistry tags automatically included

## Import Process

### For Each Paper

**Step 1: Extract DOI**
- Tries to extract DOI from URL column
- Supports formats:
  - `https://doi.org/10.1016/...`
  - `https://www.sciencedirect.com/.../10.1016/...`
  - Plain DOI: `10.1016/j.jpowsour.2024...`

**Step 2: Check Duplicates**
- Compares DOI with existing papers (if available)
- Compares title with 90% similarity threshold
- Skips if already in library (optional)

**Step 3: Fetch Metadata**
- Fetches full metadata from CrossRef (if DOI available)
- Falls back to CSV metadata if CrossRef fails
- Includes: title, authors, year, journal, abstract, etc.

**Step 4: Search for PDF**
- Searches Semantic Scholar for open access PDF
- Falls back to Unpaywall API
- Downloads PDF if available
- Saves as metadata-only if no PDF found

**Step 5: Save to Library**
- Saves metadata to `data/metadata.json`
- Adds to ChromaDB for search
- Marks as `pdf_status: "available"` or `"needs_pdf"`

## Rate Limiting

**Delays between papers:**
- 2.5 seconds between each paper
- Prevents API rate limits for:
  - CrossRef metadata API
  - Semantic Scholar API
  - Unpaywall API

**Why this matters:**
- CrossRef: No rate limit with delays
- Semantic Scholar: 100 requests per 5 min (without API key)
- Unpaywall: No explicit limit, but respectful delays

**Import time estimates:**
- 10 papers: ~30 seconds
- 50 papers: ~2.5 minutes
- 100 papers: ~5 minutes
- 1,634 papers: ~2 hours (in batches)

## Batch Processing Strategy

### Start Small
```
Batch 1: 5 papers (test run)
  ↓
Check results
  ↓
Batch 2: 10 papers (if successful)
  ↓
Check results
  ↓
Batch 3: 25 papers (if working well)
  ↓
Continue with larger batches
```

### Recommended Batch Sizes

- **Testing**: 5-10 papers
- **Regular import**: 25-50 papers
- **Bulk import**: 50-100 papers (watch for API limits)

### Why Batch Processing?

1. **Test first** - Verify format and duplicate detection
2. **Monitor progress** - See what's working/failing
3. **Avoid timeouts** - Large batches may timeout
4. **API respect** - Prevents overwhelming APIs
5. **Recover from errors** - Easier to resume if something fails

## Progress Tracking

### During Import

**Progress Bar:**
```
████████████████████ 8/10 (80%)
Processing paper 8 of 10...
```

**Status Updates:**
```
📥 Importing: Battery degradation mechanisms in lithium-ion...
✓ 📄 Added: Battery degradation mechanisms in lithium-ion...
   (with PDF downloaded)
```

**Indicators:**
- `📥` - Currently importing
- `✓ 📄` - Successfully added with PDF
- `✓ 📝` - Successfully added (metadata-only)
- `⏭️` - Skipped (duplicate)
- `⚠️` - Warning (no title, skipped)
- `❌` - Failed (error during import)

### After Import

**Summary Metrics:**
```
📊 Import Summary

✅ Imported    ⏭️ Skipped    ❌ Failed
    8             1            1
```

**Auto-refresh:**
- App refreshes after successful import
- New papers appear in Library tab
- Ready for next batch

## Duplicate Detection

### How It Works

**DOI Matching (Primary):**
- Exact match: `10.1016/j.jpowsour.2024.234567`
- Case-insensitive comparison
- Most reliable method

**Title Matching (Fallback):**
- Normalized title comparison
- Removes punctuation, lowercase
- 90% word overlap threshold
- Handles slight variations

**Example:**
- CSV: "Battery Degradation in Li-Ion Cells"
- Library: "Battery degradation in lithium-ion cells"
- Match: YES (90%+ similarity)

### Skip Duplicates Option

**Enabled (default):**
- Skips papers already in library
- Shows "⏭️ Skipped: [title] (already in library)"
- Saves time and avoids duplicates

**Disabled:**
- Attempts to import all papers
- May create duplicates (not recommended)
- Useful for re-importing with updated metadata

## Error Handling

### Common Issues

**1. No Title**
```
⚠️ Row 5: No title, skipping
```
**Solution:** CSV row missing title field, skipped automatically

**2. Invalid DOI**
```
✓ 📝 Added: [title] (metadata-only)
```
**Solution:** No DOI extracted, uses CSV metadata only

**3. CrossRef Fetch Failed**
```
✓ 📝 Added: [title] (metadata-only)
```
**Solution:** Falls back to CSV metadata, continues import

**4. PDF Download Failed**
```
✓ 📝 Added: [title] (metadata-only)
```
**Solution:** No open access PDF found, saves as metadata-only

**5. Rate Limit Exceeded**
```
❌ Failed: [title] - Rate limit exceeded
```
**Solution:** Wait 5 minutes, then resume with next batch

## Example: Importing Notion Export

### Step 1: Extract CSV

```
C:\Users\rcmas\Downloads\
  └─ 02bfdb90-..._ExportBlock-....zip
      └─ [Extract]
          └─ Export-bccdef9a-....zip
              └─ [Extract]
                  ├─ Export-bccdef9a-..._all.csv  ← This one!
                  └─ Export-bccdef9a-..._other.csv
```

### Step 2: Upload to Import Tab

1. Open app → Import tab
2. Scroll to "Import from CSV"
3. Click "Upload CSV file"
4. Select `Export-bccdef9a-..._all.csv`
5. See: "✓ Loaded 1634 papers from CSV"

### Step 3: Preview Data

**Preview shows first 5 rows:**
```
Title                          URL                  Authors         Year
Battery degradation...         https://doi.org/...  Smith et al.    2024
State of health estimation...  https://doi.org/...  Johnson et al.  2023
...
```

### Step 4: Configure Import

**Batch size:** 10 (start small)
**Skip duplicates:** ✓ Checked

**Status:** "Will import up to 10 papers"

### Step 5: Import First Batch

Click "📥 Import Papers from CSV"

**Progress:**
```
████████████ 6/10 (60%)
Processing paper 6 of 10...

✓ 📄 Added: Battery degradation mechanisms...
✓ 📝 Added: State of health estimation methods...
⏭️ Skipped: Lithium-ion battery aging... (already in library)
...
```

### Step 6: Review Summary

```
📊 Import Summary

✅ Imported    ⏭️ Skipped    ❌ Failed
    8             1            1
```

**Analysis:**
- 8 new papers added
- 1 duplicate skipped
- 1 failed (check error message)

### Step 7: Import More Batches

1. Upload CSV again (or keep it uploaded)
2. Increase batch size to 25-50
3. Click import again
4. Repeat until all papers imported

**Progress tracking:**
- Batch 1: Papers 1-10 ✓
- Batch 2: Papers 11-50 ✓
- Batch 3: Papers 51-100 ✓
- ... continue ...
- Batch 33: Papers 1601-1634 ✓

## Tips & Best Practices

### 1. Test with Small Batch First
Always start with 5-10 papers to verify:
- CSV format is correct
- DOI extraction works
- Duplicate detection works
- No errors occur

### 2. Monitor the Results
Watch the status messages during import:
- Green (✓) = Success
- Blue (⏭️) = Duplicate (expected)
- Red (❌) = Error (investigate)

### 3. Handle Rate Limits Gracefully
If you see "Rate limit exceeded":
- Stop importing
- Wait 5 minutes
- Continue with next batch

### 4. Use Skip Duplicates
Keep "Skip duplicates" enabled to:
- Avoid re-importing same papers
- Save time
- Keep library clean

### 5. Import in Sessions
For large datasets (1,000+ papers):
- Import 50-100 papers per session
- Take breaks between sessions
- Monitor disk space for PDFs

### 6. Check Library After Each Batch
After each batch:
- Go to Library tab
- Verify papers imported correctly
- Check PDF availability
- Review metadata quality

### 7. Keep Original CSV
Save your original CSV file:
- Resume import if interrupted
- Re-import with different settings
- Reference original data

## Troubleshooting

### "Error reading CSV"
- Check CSV file encoding (should be UTF-8)
- Verify CSV has headers
- Ensure no special characters in filenames

### "No papers were imported"
- Check if all papers are duplicates
- Verify CSV has Title column
- Ensure batch size > 0

### Many papers failing
- Check network connection
- Verify URLs/DOIs are valid
- Try smaller batch size
- Wait if rate limited

### PDFs not downloading
- Many papers may not have open access PDFs
- This is normal - they'll be saved as metadata-only
- You can manually upload PDFs later

## Advanced Usage

### Custom CSV Formats

If your CSV has different column names, modify the import function to recognize them. Look for this section in `import_csv_papers()`:

```python
title = csv_paper.get('Title', csv_paper.get('title', '')).strip()
url = csv_paper.get('URL', csv_paper.get('url', '')).strip()
# Add more variations as needed
```

### Batch Automation

For very large imports, you can:
1. Split CSV into smaller files (100 papers each)
2. Import each file separately
3. Script the upload process

### Re-importing with Updated Metadata

To update existing papers:
1. Disable "Skip duplicates"
2. Import CSV again
3. New metadata will overwrite old

## Summary

The CSV import feature provides:

✅ **Bulk import** - Process hundreds of papers at once
✅ **DOI extraction** - Automatically extracts DOIs from URLs
✅ **Metadata fetching** - Full metadata from CrossRef
✅ **PDF discovery** - Searches Semantic Scholar + Unpaywall
✅ **Duplicate detection** - DOI and title-based matching
✅ **Progress tracking** - Visual feedback during import
✅ **Rate limiting** - Respects API limits automatically
✅ **Batch processing** - Import in manageable chunks
✅ **Error handling** - Continues despite individual failures
✅ **Flexible format** - Recognizes various column names

**Perfect for:**
- Notion paper database exports
- Reference manager exports (Zotero, Mendeley)
- Custom paper lists
- Literature review collections
- Grant proposal paper lists

**Status: PRODUCTION READY** 🎉

---

**Your Next Steps:**

1. Extract your Notion export CSV
2. Go to Import tab → "Import from CSV"
3. Upload the `_all.csv` file
4. Start with batch size 10
5. Review results
6. Continue importing in batches of 25-50
7. All 1,634 papers imported! 🎉
