# Test Plan: UI Improvements (DOI + AG Grid)

## Pre-Test Setup

1. Wait for metadata extraction to complete (~5 minutes)
2. Re-run embed stage: `python scripts/ingest_pipeline.py --stage embed --force`
3. Start Streamlit: `streamlit run app.py`

## Test Cases

### Test 1: DOI Column Visibility
**Steps:**
1. Open library view
2. Look for DOI column in table

**Expected:**
- DOI column appears between Journal and Read columns
- Papers with DOI show the DOI value
- Papers without DOI show "—"

### Test 2: DOI Links (Clickable)
**Steps:**
1. Find a paper with a DOI
2. Click on the DOI link

**Expected:**
- Link opens in new tab
- Opens to https://doi.org/{DOI}
- Link has blue color (#1f77b4)

### Test 3: AG Grid Sorting
**Steps:**
1. Click on "Year" column header
2. Click again to reverse sort
3. Try sorting by Title, Authors, Journal

**Expected:**
- Table sorts by clicked column
- Arrow indicator shows sort direction
- Multiple clicks toggle between ascending/descending

### Test 4: AG Grid Column Resizing
**Steps:**
1. Hover over column edge (between Title and Authors)
2. Drag to resize column

**Expected:**
- Cursor changes to resize cursor
- Column width adjusts as you drag
- Adjacent columns adjust accordingly

### Test 5: Row Selection (Detail View)
**Steps:**
1. Click anywhere on a paper row
2. Should navigate to detail view

**Expected:**
- Detail view opens for selected paper
- Shows all paper metadata
- DOI appears in bibliographic info section

### Test 6: Read Checkbox
**Steps:**
1. Click checkbox in Read column for unread paper
2. Refresh page
3. Check if status persists

**Expected:**
- Checkbox shows ✓ when checked
- Status persists after page refresh
- Database updated (check with read_status.py)

### Test 7: Grid Hover Effects
**Steps:**
1. Hover mouse over different rows

**Expected:**
- Row highlights on hover
- Background changes to light gray (#f8f9fa)
- Hover effect removed when mouse leaves

### Test 8: DOI in Detail View
**Steps:**
1. Open a paper detail view
2. Look for DOI in bibliographic section

**Expected:**
- DOI appears after Year and Journal
- Shows as clickable link if available
- Shows "Not available" if no DOI

### Test 9: Grid Performance
**Steps:**
1. Scroll through all 9 papers
2. Sort by different columns
3. Resize columns

**Expected:**
- Smooth scrolling
- No lag when sorting
- Responsive column resizing

### Test 10: Tooltips
**Steps:**
1. Hover over Title cell with long title
2. Hover over Authors cell with many authors
3. Hover over Journal cell with long name

**Expected:**
- Tooltip appears showing full text
- Tooltip appears after ~1 second hover
- Tooltip disappears when mouse moves

## Verification Queries

### Check DOI Extraction Success
```bash
cd "C:\Users\rcmas\astrolabe-paper-db"
python -c "
import json
data = json.load(open('data/metadata.json'))
papers_with_doi = [f for f, m in data.items() if m.get('doi')]
print(f'Papers with DOI: {len(papers_with_doi)}/{len(data)}')
for filename, metadata in data.items():
    if metadata.get('doi'):
        print(f\"  {filename}: {metadata['doi']}\")
"
```

### Check ChromaDB has DOI
```bash
python -c "
from lib import rag
papers = rag.get_paper_library()
papers_with_doi = [p for p in papers if p.get('doi')]
print(f'Papers with DOI in library: {len(papers_with_doi)}/{len(papers)}')
for p in papers_with_doi[:3]:
    print(f\"  {p['title'][:50]}...: {p['doi']}\")
"
```

## Known Issues to Watch For

### DOI Extraction
- Some PDFs may not have DOIs
- DOIs in unusual formats may not be detected
- Expect ~50-80% DOI detection rate for academic papers

### AG Grid
- First load may be slightly slower than manual table
- Checkbox editing causes brief re-render flash
- Very long titles may overflow despite truncation

### Styling
- Dark mode support may need adjustment
- Mobile view may need responsive tweaks
- Print view may need CSS adjustments

## Success Criteria

- [ ] All 9 papers display in AG Grid table
- [ ] At least 5 papers have DOI extracted
- [ ] DOI links are clickable and open in new tab
- [ ] Sorting works for all columns
- [ ] Column resizing works smoothly
- [ ] Row selection navigates to detail view
- [ ] Read checkbox updates and persists
- [ ] Hover effects work correctly
- [ ] Performance is smooth (no lag)
- [ ] Detail view shows DOI for papers that have it

## Rollback Plan (If Issues Found)

If major issues occur:

1. Revert app.py changes:
   ```bash
   git checkout HEAD -- app.py
   ```

2. Keep DOI extraction changes (they're useful even without UI)

3. Restart Streamlit:
   ```bash
   streamlit run app.py
   ```

## Post-Test Actions

After successful testing:

1. Commit changes:
   ```bash
   git add .
   git commit -m "Add DOI column and AG Grid table component"
   git push
   ```

2. Update documentation:
   - Add AG Grid to requirements.txt
   - Update README with new UI features
   - Document DOI extraction in pipeline docs

3. Optional enhancements:
   - Add column filtering
   - Add export to CSV feature
   - Add bulk operations (mark all as read)
