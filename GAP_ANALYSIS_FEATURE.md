# Gap Analysis Feature Guide

## Overview
The Gap Analysis feature identifies frequently cited papers that are missing from your library. By analyzing references across all papers in your collection, it discovers which papers are most often cited but not yet in your library - revealing important papers you may want to add.

## How It Works

### Reference Aggregation
1. Scans all papers in your library
2. Extracts references from each paper's reference list
3. Aggregates references across all papers
4. Counts how many times each reference appears
5. Filters out papers already in your library
6. Ranks by citation frequency

### Matching Logic
**By DOI (Primary):**
- Normalizes DOIs (removes URL prefixes, lowercase)
- Exact DOI matching is most reliable

**By Title (Fallback):**
- Normalizes titles (lowercase, whitespace)
- Uses fuzzy matching (90% similarity threshold)
- Handles minor variations in titles

### Library Exclusion
References are excluded if:
- DOI matches a paper in your library
- Title closely matches a paper in your library (90%+ similarity)

## Features

### Statistics Dashboard
- **Total Missing Papers**: Count of unique references not in library
- **Total Citations**: Sum of all citations to missing papers
- **Avg Citations/Paper**: Average citation count per missing paper
- **Top Paper Citations**: Citation count of most-cited missing paper

### Ranked List
Shows top 20 most-cited missing papers with:
- **Rank**: 1-20 based on citation count
- **Title**: Full paper title
- **Authors**: Author list (truncated if long)
- **Year**: Publication year
- **Journal**: Journal name (if available)
- **DOI**: Clickable link to DOI.org
- **Citation Count**: Number of papers in your library that cite this
- **Import Button**: One-click import via DOI

### Cited By Details
For each suggested paper, expandable section shows:
- List of papers in your library that cite this reference
- Helps understand why this paper is relevant to your research

## Using Gap Analysis

### Accessing the Feature
1. Open the app
2. Navigate to the "📊 Gap Analysis" tab (2nd tab)
3. Wait for analysis to complete (a few seconds)

### Interpreting Results

**High Citation Count (5+ citations):**
- Core/foundational papers in your research area
- Methods papers frequently referenced
- Review papers that provide overview
- **Action**: Strong candidates for import

**Medium Citation Count (2-4 citations):**
- Important supporting papers
- Specialized methodology papers
- Related research areas
- **Action**: Consider for import based on relevance

**Low Citation Count (1 citation):**
- Tangential references
- Less central to your research focus
- **Action**: Import if specifically needed

### Importing Papers

**With DOI:**
1. Click "📥 Import" button next to paper
2. System fetches metadata from CrossRef API
3. Paper added as metadata-only entry
4. View in Library tab immediately

**Without DOI:**
- Import button disabled
- Must add manually via URL/DOI in Library tab
- Copy title and search online for PDF/DOI

## Use Cases

### 1. Literature Review
Identify key papers cited frequently in your field that you haven't read yet.

### 2. Research Foundation
Find foundational papers that your references build upon.

### 3. Methods Papers
Discover important methodology papers cited across your collection.

### 4. Gap Coverage
Ensure comprehensive coverage of your research area by identifying missing core papers.

### 5. Citation Network
Build out your citation network by adding frequently referenced works.

## Technical Details

### Module: `lib/gap_analysis.py`

**Key Functions:**
- `analyze_reference_gaps()` - Main analysis function
- `get_top_gaps(n=20)` - Get top N missing papers
- `get_gap_statistics()` - Calculate statistics
- `normalize_doi()` - DOI normalization
- `normalize_title()` - Title normalization
- `titles_match()` - Fuzzy title matching

**Data Structure:**
```python
{
    'title': str,           # Paper title
    'authors': str,         # Author list
    'year': str,            # Publication year
    'journal': str,         # Journal name
    'doi': str,             # DOI (if available)
    'citation_count': int,  # Times cited in library
    'cited_by': List[str]   # Titles of citing papers
}
```

### Performance
- Analysis runs on-demand (when tab opened)
- Typically completes in 2-5 seconds for 100-500 papers
- Results cached during session
- No persistent storage (recalculated each time)

### Accuracy
**High Accuracy (DOI-based):**
- Exact matching via normalized DOI
- Reliable identification
- No false positives

**Good Accuracy (Title-based):**
- Fuzzy matching at 90% threshold
- Handles minor variations
- May miss papers with very different titles
- Very rare false negatives

### Edge Cases Handled
1. **Incomplete references** - Skipped if missing title or author
2. **No DOI** - Falls back to title matching
3. **Already in library** - Filtered out by DOI or title match
4. **Multiple citations** - Correctly aggregates count
5. **Empty library** - Returns empty list gracefully

## Limitations

1. **Requires extracted references**
   - Only works if papers have references extracted
   - New papers may not have references yet

2. **Metadata quality**
   - Depends on quality of reference extraction
   - Incomplete references skipped

3. **No PDF availability check**
   - Shows papers that may not have free PDFs
   - Import may require manual PDF download

4. **CrossRef dependency**
   - Import requires CrossRef API
   - May fail for papers not in CrossRef
   - Requires internet connection

5. **No automatic updates**
   - Analysis runs on-demand only
   - Must refresh tab to update results

## Tips for Best Results

1. **Let references extract first**
   - Wait for ingestion to complete with reference extraction
   - Check papers have references in detail view

2. **Review top 5-10 first**
   - Most cited papers are usually most important
   - Focus on high citation counts initially

3. **Check "Cited By" section**
   - Understand why paper is relevant
   - See which of your papers reference it

4. **Import in batches**
   - Don't import all 20 at once
   - Import most relevant 5-10 first
   - Review and add more later

5. **Use Library filters after import**
   - Filter by metadata-only status
   - Prioritize getting PDFs for imported papers

## Future Enhancements (Potential)

- Auto-refresh when new papers added
- Filter by citation threshold
- Export gap list to CSV/BibTeX
- Batch import multiple papers
- Show citation network graph
- Smart recommendations based on reading history
- PDF availability checking
- Alternative identifier support (arXiv, PubMed)

## Example Scenario

**Your Library:**
- 50 papers on battery degradation
- Many cite the same foundational papers
- Some key papers missing

**Gap Analysis Shows:**
1. "Battery Degradation Mechanisms" - cited 8 times
2. "SOH Estimation Methods" - cited 7 times
3. "Lithium Plating Study" - cited 6 times

**Action:**
- Import top 3 papers via DOI
- Read abstracts to confirm relevance
- Download PDFs for key papers
- Update collections to organize

**Result:**
- More complete literature coverage
- Better understanding of field foundations
- Improved research context

---

**Implementation Date:** 2026-02-05
**Version:** 1.0
**Status:** Production Ready
