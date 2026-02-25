# Frequently Cited Papers - Add to Library Feature

**Date:** 2026-02-05
**Status:** ✅ Complete and Ready

## Overview

Added "Add to Library" functionality to the "Frequently Cited Papers You Don't Have" section with checkbox selection, batch import, and automatic PDF search via Semantic Scholar and Unpaywall.

## Features Implemented

### 1. Multi-Select with Checkboxes

**AG Grid Configuration:**
- Changed from single-select to multi-select mode
- Added checkboxes for each row
- Suppressed row click selection (only checkbox selects)

**User Experience:**
- Check boxes next to papers you want
- Select one or multiple papers
- Clear visual selection state

### 2. Action Buttons

**"Add Selected" Button (Primary):**
- Adds only the checked papers
- Primary button (blue, prominent)
- Shows count in progress spinner
- Displays success summary

**"Add All" Button (Secondary):**
- Adds all 20 papers at once
- Secondary button (gray)
- Requires confirmation (two-click)
- Shows warning before adding

**Tip Message:**
- "💡 Tip: Check boxes to select papers, then use buttons below"
- Appears above buttons
- Guides users to checkbox interface

### 3. Automatic PDF Search

**Multi-Source PDF Discovery:**

**Source 1: Semantic Scholar**
- Searches by DOI first
- Checks for open access status
- Gets PDF URL if available
- Fast and reliable

**Source 2: Unpaywall (Fallback)**
- Queries Unpaywall API if Semantic Scholar fails
- Checks `is_oa` flag
- Gets `best_oa_location.url_for_pdf`
- No API key required

**PDF Download:**
- Automatic download if PDF found
- Saves to `papers/` directory
- Uses semantic_scholar.download_pdf()
- Handles failures gracefully

### 4. Metadata Management

**With PDF:**
- Saves paper to `papers/`
- Sets `metadata_only: false`
- Sets `pdf_status: "available"`
- Full paper entry

**Without PDF:**
- Creates metadata-only entry
- Sets `metadata_only: true`
- Sets `pdf_status: "needs_pdf"`
- Marks for later PDF addition

**Metadata Fields:**
- Title, authors, year, journal
- DOI, abstract, keywords
- Volume, issue, pages
- References list
- Date added

### 5. Progress Feedback

**During Import:**
- Spinner with count: "Adding 3 paper(s)..."
- Individual paper processing
- Handles errors per paper

**After Import:**
- Success message: "✓ Added 5 of 7 paper(s)"
- Shows success count vs total
- Auto-refreshes after 2 seconds
- Updates library immediately

**Error Handling:**
- Continues even if some papers fail
- Reports total success count
- Doesn't stop on individual errors

## Implementation Details

### New Function: `add_paper_with_pdf_search()`

**Location:** `app.py` (after `save_metadata_only_paper()`)

**Parameters:**
- `doi` - Paper DOI
- `title` - Paper title
- `authors` - Authors string
- `year` - Publication year

**Returns:**
```python
{
    'success': bool,
    'message': str,
    'pdf_found': bool
}
```

**Process Flow:**
```
1. Get metadata from CrossRef (if DOI available)
   ↓
2. Search Semantic Scholar for open access PDF
   ↓
3. If no PDF, try Unpaywall API
   ↓
4. Download PDF if found
   ↓
5. Save metadata (with or without PDF)
   ↓
6. Add to ChromaDB
   ↓
7. Return success/failure
```

### Modified Components

**AG Grid Configuration:**
```python
gb.configure_selection(
    selection_mode="multiple",
    use_checkbox=True
)

gb.configure_grid_options(
    suppressRowClickSelection=True  # Checkbox-only selection
)
```

**Button Handlers:**
- Check for selected rows
- Show warning if none selected
- Process each paper
- Collect results
- Show summary
- Rerun to refresh

## Usage Examples

### Example 1: Add Selected Papers

1. Open Discover tab
2. Scroll to "Frequently Cited Papers"
3. Check 3-5 papers you want
4. Click "📥 Add Selected"
5. Wait for import (5-15 seconds)
6. See "✓ Added 5 of 5 papers"
7. Papers appear in Library

### Example 2: Add All Papers

1. Open Discover tab
2. Scroll to "Frequently Cited Papers"
3. Click "📥 Add All"
4. See warning: "Click again to confirm"
5. Click "📥 Add All" again
6. Wait for import (30-60 seconds)
7. See "✓ Added 20 of 20 papers"
8. All papers added to Library

### Example 3: Mixed Success

1. Select 10 papers (some with DOIs, some without)
2. Click "📥 Add Selected"
3. System tries to find PDFs for all
4. Some succeed, some fail
5. See "✓ Added 7 of 10 papers"
6. 7 papers added successfully

## PDF Search Logic

### Semantic Scholar Search

**Query:**
```python
search_papers(query=f'doi:{doi}', limit=1)
```

**Check:**
- `is_open_access == True`
- `pdf_url` is not empty

**Success:**
- Download PDF
- Set `pdf_status: "available"`

### Unpaywall Fallback

**API Endpoint:**
```
https://api.unpaywall.org/v2/{doi}?email=user@example.com
```

**Check:**
- `is_oa == True`
- `best_oa_location.url_for_pdf` exists

**Success:**
- Download PDF
- Set `pdf_status: "available"`

### No PDF Found

**Fallback:**
- Save metadata-only
- Set `pdf_status: "needs_pdf"`
- User can add PDF manually later

## Benefits

### 1. Efficient Batch Import
- Add multiple papers at once
- No manual searching
- No individual clicks

### 2. Automatic PDF Discovery
- Finds open access PDFs automatically
- Two sources (Semantic Scholar + Unpaywall)
- No manual PDF hunting

### 3. Smart Fallback
- Still adds paper even without PDF
- Marks as "needs_pdf" for later
- Doesn't lose valuable metadata

### 4. Clear Feedback
- Shows progress during import
- Reports success count
- Handles errors gracefully

### 5. Seamless Integration
- Works with existing library
- Updates immediately
- No manual refresh needed

## Rate Limiting Considerations

**Semantic Scholar:**
- Already has rate limiting (2 sec without key)
- Respects existing limits
- May slow down for many papers

**Unpaywall:**
- No explicit rate limit in code
- API is generally lenient
- Handles 20 requests easily

**Recommendation:**
- Use "Add Selected" for <10 papers
- Use "Add All" carefully (20 API calls)
- Wait if rate limited

## Error Scenarios Handled

### 1. No DOI
- Uses provided metadata
- Skips PDF search (needs DOI)
- Saves as metadata-only

### 2. CrossRef Fails
- Falls back to provided metadata
- Continues with PDF search
- Still adds paper

### 3. Semantic Scholar Fails
- Tries Unpaywall
- Continues with fallback
- Still adds paper

### 4. Unpaywall Fails
- Saves metadata-only
- Marks as "needs_pdf"
- No data loss

### 5. PDF Download Fails
- Falls back to metadata-only
- Marks as "needs_pdf"
- Metadata still saved

### 6. Save Fails
- Returns error in result
- Continues with other papers
- Reports in summary

## Testing

### Test 1: Checkbox Selection
```
✓ Checkboxes appear in grid
✓ Can select multiple papers
✓ Selection persists
✓ Buttons respond to selection
```

### Test 2: Add Selected
```
✓ Button only works with selection
✓ Shows warning if none selected
✓ Processes all selected papers
✓ Shows success count
✓ Refreshes library
```

### Test 3: Add All
```
✓ Requires confirmation
✓ Shows warning on first click
✓ Processes all 20 papers
✓ Shows success count
✓ Refreshes library
```

### Test 4: PDF Search
```
✓ Semantic Scholar module imported
✓ Unpaywall API accessible
✓ PDF download works
✓ Fallback to metadata-only works
```

## Comparison with References Table

### Similarities
- Checkbox selection
- Multi-select mode
- Batch import capability
- Clear UI feedback

### Differences
- **PDF Search:** Automatically searches for PDFs
- **Two Sources:** Uses Semantic Scholar + Unpaywall
- **Status Tracking:** Marks papers with pdf_status
- **Confirmation:** "Add All" requires confirmation

## Future Enhancements

Potential improvements:
- [ ] Show PDF availability before adding
- [ ] Preview abstract before adding
- [ ] Filter by citation threshold
- [ ] Export selection to BibTeX
- [ ] Track import success rate
- [ ] Retry failed imports
- [ ] Custom PDF sources

## Summary

The "Add to Library" feature for Frequently Cited Papers provides:

✅ **Multi-select:** Check boxes for flexible selection
✅ **Batch import:** Add multiple papers at once
✅ **PDF search:** Automatic open access PDF discovery
✅ **Dual sources:** Semantic Scholar + Unpaywall
✅ **Smart fallback:** Saves metadata even without PDF
✅ **Clear feedback:** Progress and success reporting
✅ **Error handling:** Continues despite failures

**Perfect for:**
- Quickly building literature collection
- Finding foundational papers with PDFs
- Batch importing gap papers
- Efficient library expansion

**Status: PRODUCTION READY** 🎉

---

**Try it now:**
1. Open Discover tab
2. Scroll to "Frequently Cited Papers"
3. Check a few papers
4. Click "Add Selected"
5. Watch papers import with PDFs! ✓
