# UI Improvements Summary

**Date:** 2026-02-04
**Changes:** DOI column + AG Grid implementation

## Overview

Improved the library view with two major enhancements:
1. DOI column with clickable links
2. Professional AG Grid table component

## Changes Made

### 1. DOI Support

#### Pipeline (scripts/ingest_pipeline.py)
- Added `'doi': ''` to default metadata dict
- DOI always saved when extracted (even if CrossRef fails)
- DOI stored in ChromaDB metadata for all chunks

#### Legacy Script (scripts/ingest.py)
- Updated to include DOI in metadata dict
- DOI stored in ChromaDB (consistency with new pipeline)

#### Library Backend (lib/rag.py)
- `get_paper_library()`: Added DOI field to paper dict
- `get_paper_details()`: Added DOI field to details dict

### 2. AG Grid Table Component

#### Installation
```bash
pip install streamlit-aggrid
```

#### Implementation (app.py)

**Replaced:** Manual table with st.columns() and st.button()
**With:** AG Grid component with:
- Sortable columns (click headers)
- Resizable columns (drag edges)
- Row selection (click to view details)
- Editable Read checkbox
- Hover highlighting
- Compact, professional appearance

**Column Configuration:**
- **Title** (350px) - Sortable, truncated with tooltip
- **Authors** (250px) - Shows first 3 + "et al.", tooltip for full list
- **Year** (80px) - Numeric sort
- **Journal** (200px) - Truncated with tooltip
- **DOI** (150px) - **Clickable link** to https://doi.org/{DOI}
- **Read** (70px) - Editable checkbox

**Features:**
- Clickable DOI links open in new tab
- Row selection opens paper detail view
- Edit Read checkbox to mark as read/unread
- Grid height: 600px (fits ~17 papers without scrolling)
- Row height: 35px (compact, readable)
- Professional styling with subtle hover effects

#### Detail View Updates
- Added DOI display with clickable link
- Format: `[DOI](https://doi.org/{DOI})`
- Shows "Not available" if no DOI

## Technical Details

### DOI Link Implementation
Used JavaScript cell renderer for clickable links:
```javascript
function(params) {
    if (params.value === '—' || params.value === '') {
        return '—';
    }
    const doi = params.value;
    const url = params.data._doi_url;
    return '<a href="' + url + '" target="_blank"
            style="color: #1f77b4; text-decoration: none;">'
            + doi + '</a>';
}
```

### Read Checkbox Implementation
- Checkbox renderer shows ✓ when checked
- Editable via AG Grid's built-in checkbox editor
- Updates read status in SQLite database
- Auto-refresh on change

### Grid Styling
```python
custom_css = {
    ".ag-header-cell-label": {"font-weight": "600", "color": "#2c3e50"},
    ".ag-row": {"border-bottom": "1px solid #ecf0f1"},
    ".ag-row-hover": {"background-color": "#f8f9fa !important"},
    ".ag-cell": {"line-height": "35px", "padding": "0 8px"},
}
```

## Data Migration

### Re-extract Metadata with DOI
```bash
# Re-extract metadata to populate DOI fields
python scripts/ingest_pipeline.py --stage metadata --force

# Re-embed with updated metadata
python scripts/ingest_pipeline.py --stage embed --force
```

**Duration:** ~5 minutes for 9 papers

## Benefits

### DOI Column
- **Direct access** to paper DOI links
- **Discoverability** - see which papers have DOIs
- **Validation** - verify correct paper identification
- **Citation** - easy access to canonical reference

### AG Grid
- **Professional appearance** - looks like Mendeley/Zotero
- **Better UX** - sortable, resizable columns
- **Performance** - handles large datasets efficiently
- **Interactivity** - native grid features (sorting, filtering, selection)
- **Accessibility** - keyboard navigation, screen reader support

## Comparison: Before vs After

### Before
- Manual table with st.columns()
- Fixed column widths
- No sorting capability
- Button-based title selection
- No DOI information
- Checkbox in separate column

### After
- AG Grid component
- Resizable columns by dragging
- Sort by any column (click header)
- Row selection (click anywhere)
- DOI links (clickable, open in new tab)
- Integrated read checkbox (editable in place)
- Professional reference manager appearance

## Testing

### Test DOI Links
1. Start Streamlit: `streamlit run app.py`
2. Verify DOI column appears
3. Click DOI links - should open https://doi.org/{DOI} in new tab
4. Papers without DOI show "—"

### Test Grid Features
1. **Sorting:** Click column headers to sort
2. **Resizing:** Drag column edges to resize
3. **Selection:** Click row to open detail view
4. **Read status:** Check/uncheck Read checkbox
5. **Hover:** Hover over rows for highlight
6. **Tooltips:** Hover over cells for full text

### Test Data Consistency
```python
from lib import rag
papers = rag.get_paper_library()
print(papers[0])  # Should have 'doi' field
```

## Future Enhancements

### AG Grid Features
- [ ] Column filtering (filter by year, journal, etc.)
- [ ] Column pinning (pin Title column while scrolling)
- [ ] Export to CSV/Excel
- [ ] Bulk operations (mark multiple as read)
- [ ] Custom row height (user preference)
- [ ] Save grid state (column order, widths)

### DOI Features
- [ ] Bulk DOI extraction for papers without DOI
- [ ] DOI validation (check if DOI resolves)
- [ ] Alternative identifiers (arXiv, PubMed ID)
- [ ] Copy DOI to clipboard button

## Files Modified

1. **scripts/ingest_pipeline.py** - DOI extraction and storage
2. **scripts/ingest.py** - DOI support in legacy script
3. **lib/rag.py** - DOI retrieval from database
4. **app.py** - AG Grid implementation + DOI links
5. **requirements.txt** (should add) - streamlit-aggrid

## Dependencies

Add to requirements.txt:
```
streamlit-aggrid>=1.2.0
```

## Configuration

### Grid Options
Customize in app.py:
- `rowHeight` - Row height in pixels (default: 35)
- `headerHeight` - Header height in pixels (default: 40)
- `height` - Grid height in pixels (default: 600)
- Column widths - Adjust width parameter for each column

### Styling
Customize `custom_css` dict in app.py for:
- Header colors
- Row hover colors
- Border styles
- Cell padding

## Known Issues

### Checkbox Editing
- Grid re-renders on checkbox change (expected behavior)
- Brief flash during re-render (Streamlit limitation)

### DOI Links
- Requires `allow_unsafe_jscode=True` for clickable links
- Links open in new tab (browser popup blocker may interfere)

### Performance
- Grid loads quickly for 9 papers
- May need pagination for 100+ papers

## Conclusion

The UI improvements provide a more professional, feature-rich library interface:
- DOI links enable quick access to paper sources
- AG Grid provides familiar reference manager experience
- Better UX with sortable, resizable columns
- Maintains all existing functionality (read status, detail view)

**Status:** ✓ Ready for use after metadata re-extraction completes
