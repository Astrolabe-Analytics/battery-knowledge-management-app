# Sidebar Import Section - Implementation Summary

**Date:** 2026-02-05
**Status:** ✅ Complete and Ready

## Overview

Added a new "Import" section to the sidebar with two quick-access features for adding papers to the library, accessible from any tab without navigation.

## Features Implemented

### 1. Scan for New PDFs Button

**Location:** Sidebar → Import section

**Functionality:**
- Scans `papers/` folder for PDF files
- Checks against existing metadata
- Identifies new PDFs not in library
- Shows count and list of new files

**User Experience:**
```
Click "📂 Scan for New PDFs"
   ↓
Scanning papers/ folder...
   ↓
Found 3 new PDF(s)
- paper1.pdf
- paper2.pdf
- paper3.pdf

"Run ingestion pipeline to process them"
```

**Use Cases:**
- Just dropped PDFs into papers/ folder
- Want to check what needs ingesting
- Quick scan before running pipeline
- Verify PDFs were copied correctly

### 2. Add by URL or DOI

**Location:** Sidebar → Import section (below Scan button)

**Interface:**
- Text input field
- Placeholder: "10.1016/j.jpowsour.2024..."
- Submit button: "📥 Add to Library"
- Form with auto-clear on submit

**Accepts:**
- DOI: `10.1016/j.jpowsour.2024.234567`
- DOI URLs: `https://doi.org/10.1016/...`
- Publisher URLs: `https://www.sciencedirect.com/...` (extracts DOI)
- Any URL containing a DOI pattern

**Process:**
```
1. Paste DOI or URL
   ↓
2. Extract DOI from input
   ↓
3. Fetch metadata from CrossRef
   ↓
4. Search for open access PDF
   ↓
5. Download PDF if found
   ↓
6. Add to library
   ↓
7. Show success message
```

**Features:**
- Automatic DOI extraction from URLs
- CrossRef metadata fetching
- Semantic Scholar PDF search
- Unpaywall API fallback
- Automatic PDF download
- Metadata-only fallback

## Implementation Details

### Sidebar Structure

```python
with st.sidebar:
    # Library Stats (existing)
    st.subheader("Library Stats")
    st.metric("Papers", len(papers))
    st.metric("Chunks", total_chunks)

    st.divider()

    # Import section (NEW)
    st.subheader("Import")
    st.caption("Add papers to your library")

    # Feature 1: Scan for New PDFs
    st.button("📂 Scan for New PDFs")

    # Feature 2: Add by URL or DOI
    st.form("sidebar_doi_import")
```

### Scan for New PDFs Logic

**Process:**
1. Check if `papers/` folder exists
2. Get all `*.pdf` files
3. Load `metadata.json`
4. Compare filenames
5. Identify new PDFs
6. Show list (first 5 + count)

**Error Handling:**
- Papers folder missing → Warning
- No new PDFs → Info message
- Found new PDFs → Success with list

### Add by URL or DOI Logic

**DOI Extraction:**
```python
import re
doi_match = re.search(r'10\.\d{4,}/[^\s]+', input_text)
doi = doi_match.group(0)
```

**Paper Addition:**
- Uses `add_paper_with_pdf_search()` function
- Fetches metadata via CrossRef
- Searches for PDF (Semantic Scholar + Unpaywall)
- Downloads if available
- Saves with `pdf_status` flag

**Success Messages:**
- With PDF: "✓ Paper added with PDF!"
- Without PDF: "✓ Paper added (metadata-only)" + "No open access PDF found"
- Error: Shows specific error message

## Usage Examples

### Example 1: Scan for New PDFs

**Scenario:** Dropped 3 PDFs into papers/ folder

**Steps:**
1. Open any tab (Library, Discover, Research, etc.)
2. Look at sidebar
3. Click "📂 Scan for New PDFs"
4. See: "Found 3 new PDF(s)"
5. See list of new files
6. Note: "Run ingestion pipeline to process them"

**Result:** Know which PDFs are waiting to be ingested

### Example 2: Add by DOI

**Scenario:** Found a paper DOI in a citation

**Steps:**
1. Copy DOI: `10.1016/j.jpowsour.2024.234567`
2. Open any tab
3. Go to sidebar → Import
4. Paste DOI in "Add by URL or DOI"
5. Click "📥 Add to Library"
6. Wait 5-10 seconds
7. See: "✓ Paper added with PDF!"

**Result:** Paper in library with PDF (if open access)

### Example 3: Add by URL

**Scenario:** Found paper on publisher website

**Steps:**
1. Copy URL: `https://doi.org/10.1016/j.jpowsour.2024.234567`
2. Open any tab
3. Go to sidebar → Import
4. Paste URL in input
5. Click "📥 Add to Library"
6. System extracts DOI automatically
7. See: "✓ Paper added!"

**Result:** Paper in library (DOI extracted from URL)

### Example 4: No Open Access PDF

**Scenario:** Adding a paywalled paper

**Steps:**
1. Paste DOI: `10.1016/j.somepaywall.2024.12345`
2. Click "📥 Add to Library"
3. System searches for PDF
4. No open access found
5. See: "✓ Paper added (metadata-only)"
6. See: "No open access PDF found"

**Result:** Paper metadata in library, marked as needs_pdf

## Benefits

### 1. Always Accessible

**Sidebar Advantages:**
- Visible from any tab
- No navigation needed
- Quick access
- Doesn't interrupt workflow

**Use Cases:**
- Researching and want to add paper
- Found DOI in email
- Just dropped PDFs in folder
- Quick paper addition

### 2. Streamlined Workflow

**Before:**
```
Go to Library tab
→ Scroll to upload section
→ Find DOI input
→ Paste DOI
→ Click import
```

**After:**
```
Paste DOI in sidebar
→ Click import
```

**Saved:** 3 steps, no navigation

### 3. Two Import Methods

**Method 1 (Scan):**
- For PDFs already downloaded
- Batch discovery
- Pipeline preparation

**Method 2 (DOI/URL):**
- For online papers
- One-at-a-time
- Immediate addition

### 4. Smart PDF Discovery

**Automatic Search:**
- Semantic Scholar first
- Unpaywall fallback
- Downloads if available
- Metadata-only if not

**Result:** Best effort to get PDFs automatically

## Positioning

### Sidebar Layout

```
┌─────────────────────┐
│ Library Stats       │
│ - Papers: 42        │
│ - Chunks: 1,234     │
├─────────────────────┤
│ Import              │
│                     │
│ [📂 Scan for PDFs]  │
│                     │
│ Add by URL or DOI   │
│ ┌─────────────────┐ │
│ │ Paste here...   │ │
│ └─────────────────┘ │
│ [📥 Add to Library] │
└─────────────────────┘
```

**Design Principles:**
- Grouped by function (Import)
- Clear labels
- Visual hierarchy
- Action-oriented buttons

## Error Handling

### Scan for New PDFs

**Papers folder missing:**
```
⚠️ papers/ folder not found
```

**No new PDFs:**
```
ℹ️ No new PDFs found
```

### Add by URL or DOI

**Invalid input:**
```
❌ Invalid DOI or URL format
```

**CrossRef fetch fails:**
```
❌ Could not fetch metadata from CrossRef
```

**Paper addition fails:**
```
❌ Failed: [specific error message]
```

**Success with PDF:**
```
✓ Paper added with PDF!
[Auto-refresh after 1 second]
```

**Success without PDF:**
```
✓ Paper added (metadata-only)
No open access PDF found
[Auto-refresh after 1 second]
```

## Technical Details

### Form Behavior

**Auto-clear:**
```python
st.form("sidebar_doi_import", clear_on_submit=True)
```

**Benefits:**
- Input clears after submit
- Ready for next import
- Clean UX

### DOI Extraction

**Regex Pattern:**
```python
r'10\.\d{4,}/[^\s]+'
```

**Matches:**
- `10.1016/j.jpowsour.2024.234567`
- `10.1038/s41586-024-01234-5`
- `10.1109/TII.2024.1234567`

**Handles:**
- Plain DOI
- DOI URLs (https://doi.org/...)
- Publisher URLs with DOI in path

### Integration

**Uses Existing Functions:**
- `query_crossref_for_metadata()` - Get metadata
- `add_paper_with_pdf_search()` - Add with PDF search
- Auto-rerun after success

**Consistent Behavior:**
- Same as Discover tab import
- Same as Frequently Cited import
- Unified paper addition logic

## Comparison with Other Import Methods

### Method 1: Library Tab Upload

**Pros:**
- Can upload PDF files
- Drag and drop support
- Visual file selection

**Cons:**
- Requires navigation to Library
- Must scroll to find
- Takes screen space

### Method 2: Discover Tab Search

**Pros:**
- Browse and search first
- See abstracts
- Batch import

**Cons:**
- Must navigate to Discover
- Multiple steps
- Focused on discovery

### Method 3: Sidebar Import (NEW)

**Pros:**
- Always accessible
- No navigation needed
- Quick one-shot import
- Works from any tab

**Cons:**
- One at a time (for DOI)
- No preview
- Minimal UI

**Best For:** Quick addition of known papers while working

## Future Enhancements

Potential improvements:
- [ ] BibTeX import in sidebar
- [ ] Batch DOI input (paste multiple)
- [ ] Recent imports history
- [ ] Import queue/progress
- [ ] Keyboard shortcut (Ctrl+I)
- [ ] Import from clipboard
- [ ] Direct PDF URL import

## Summary

The sidebar Import section provides:

✅ **Always accessible** - Available from any tab
✅ **Two methods** - Scan PDFs or add by DOI/URL
✅ **Smart PDF search** - Automatic open access discovery
✅ **Quick workflow** - Minimal clicks, no navigation
✅ **Error handling** - Clear feedback on issues
✅ **Auto-refresh** - Library updates immediately

**Perfect for:**
- Quick paper additions while researching
- Adding papers from citations/emails
- Checking for new PDFs
- Streamlined import workflow

**Status: PRODUCTION READY** 🎉

---

**Try it now:**
1. Look at sidebar (any tab)
2. Find "Import" section
3. Paste a DOI: `10.1016/j.jpowsour.2024.234567`
4. Click "📥 Add to Library"
5. Paper added instantly! ✓
