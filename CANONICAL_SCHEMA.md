# Canonical Import Schema - Documentation

**Date:** 2026-02-05
**Status:** ✅ Implemented

## Overview

The Canonical Import Schema provides a unified way to import papers from any source (CSV, Excel, databases, APIs) regardless of column naming conventions. All imports are normalized to our standard schema, then enriched with CrossRef metadata.

## Canonical Fields

Our library uses these standard fields internally:

```python
{
    'title': str,        # Paper title (required)
    'authors': str,      # Author names (comma-separated)
    'year': str,         # Publication year
    'journal': str,      # Journal name
    'doi': str,          # Digital Object Identifier
    'url': str,          # Paper URL
    'abstract': str,     # Paper abstract
    'chemistry': str,    # Battery chemistry (LFP, NMC, etc.)
    'topics': str,       # Research topics (comma-separated)
    'tags': str,         # Keywords/tags (comma-separated)
    'paper_type': str,   # experimental, review, simulation
    'application': str,  # EV, grid, portable, etc.
    'pdf_status': str,   # available, needs_pdf
    'date_added': str,   # ISO datetime
    'notes': str         # User notes
}
```

## Supported Import Sources

### 1. Notion CSV Export

**Auto-detected by:** `Authors / Orgs` or `Abstract/Notes` columns

**Column Mappings:**
```
Source Column          →  Canonical Field
─────────────────────────────────────────
Title                  →  title
Authors / Orgs         →  authors
Authors                →  authors
Publication Year       →  year
Year                   →  year
Journal                →  journal
URL                    →  url
Tags                   →  tags
Abstract/Notes         →  abstract
Abstract               →  abstract
Notes                  →  notes
DOI                    →  doi
```

**Example Notion CSV:**
```csv
Title,Authors / Orgs,Publication Year,Journal,URL,Tags
"Battery Degradation","Smith et al.",2024,"J Power Sources","https://doi.org/10.1016/...","LFP, SOH"
```

### 2. Battery Datasets Catalog (Excel)

**Auto-detected by:** `paper_url` or `chemistry` columns

**Column Mappings:**
```
Source Column          →  Canonical Field
─────────────────────────────────────────
title                  →  title
Title                  →  title
authors                →  authors
year                   →  year
journal                →  journal
paper_url              →  url
chemistry              →  chemistry
tags                   →  tags
doi                    →  doi
```

**Special Features:**
- Auto-detects "Battery_Datasets" sheet in Excel
- Chemistry field mapped to canonical chemistry
- Merges chemistry with tags

**Example Excel Row:**
```
title: "EIS-based SOH Estimation"
authors: "Johnson et al."
year: 2023
chemistry: "LFP"
paper_url: "https://doi.org/10.1016/..."
```

### 3. Generic (Fallback)

**Used for:** Any CSV/Excel not matching above patterns

**Column Mappings:**
```
Source Column          →  Canonical Field
─────────────────────────────────────────
title, Title, TITLE    →  title
authors, Authors       →  authors
year, Year             →  year
journal, Journal       →  journal
url, URL               →  url
doi, DOI               →  doi
abstract, Abstract     →  abstract
tags, Tags             →  tags
chemistry, Chemistry   →  chemistry
```

**Features:**
- Case-insensitive matching
- Tries common variations
- Works with most standard formats

## Import Process Flow

### Step 1: Source Detection

```python
source_type = detect_import_source(columns)
# Returns: 'notion_csv', 'battery_datasets', or 'generic'
```

**Detection Logic:**
1. Check for Battery Datasets signature (paper_url, chemistry)
2. Check for Notion signature (Authors / Orgs, Abstract/Notes)
3. Default to generic (tries common variations)

### Step 2: Schema Normalization

```python
canonical = normalize_to_canonical_schema(row_data, source_type)
```

**Process:**
1. Load appropriate column mapping
2. Map each source column to canonical field
3. Handle case-insensitive matching
4. Strip whitespace
5. Initialize empty fields

**Before (Notion CSV):**
```python
{
    'Title': 'Battery Degradation Study',
    'Authors / Orgs': 'Smith, Johnson',
    'Publication Year': '2024',
    'URL': 'https://doi.org/10.1016/j.jpowsour.2024.123'
}
```

**After (Canonical):**
```python
{
    'title': 'Battery Degradation Study',
    'authors': 'Smith, Johnson',
    'year': '2024',
    'url': 'https://doi.org/10.1016/j.jpowsour.2024.123',
    'doi': '',
    'journal': '',
    'abstract': '',
    'chemistry': '',
    'topics': '',
    'tags': '',
    'paper_type': '',
    'application': '',
    'pdf_status': '',
    'date_added': '',
    'notes': ''
}
```

### Step 3: CrossRef Enrichment

```python
canonical = enrich_from_crossref(canonical)
```

**Enrichment Process:**
1. Extract DOI from URL if not present
2. Query CrossRef API with DOI
3. Fill missing fields with CrossRef data:
   - Title (if empty)
   - Authors (if empty)
   - Year (if empty)
   - Journal (if empty)
   - Abstract (if empty)
4. Rate limiting: 2.5 sec delay
5. Continues even if enrichment fails

**Before Enrichment:**
```python
{
    'title': 'Battery Paper',
    'url': 'https://doi.org/10.1016/j.jpowsour.2024.123',
    'authors': '',
    'year': '',
    'journal': ''
}
```

**After Enrichment (from CrossRef):**
```python
{
    'title': 'Battery Degradation Mechanisms in LFP Cells',
    'url': 'https://doi.org/10.1016/j.jpowsour.2024.123',
    'doi': '10.1016/j.jpowsour.2024.123',
    'authors': 'John Smith, Jane Johnson, Bob Williams',
    'year': '2024',
    'journal': 'Journal of Power Sources',
    'abstract': 'This paper investigates...'
}
```

### Step 4: PDF Search & Import

Uses enriched canonical data to:
1. Search for open access PDF (Semantic Scholar, Unpaywall)
2. Download PDF if available
3. Save to library with all metadata

## User Interface

### Source Detection Display

When importing, users see:

```
📋 Import Source Detected: Notion Csv
   Columns: Title, Authors / Orgs, Publication Year, Journal, URL, Tags

🔍 Column Mapping Preview (expandable)
{
  "title": "Battery Degradation Study",
  "authors": "Smith, Johnson",
  "year": "2024",
  "url": "https://doi.org/10.1016/...",
  "tags": "LFP, SOH"
}
```

### Import Progress

Shows enrichment in action:

```
Processing paper 3 of 10...
📥 Importing: Battery Degradation Study...
   ↓ Normalized to canonical schema
   ↓ Enriched with CrossRef metadata
   ↓ Searching for PDF...
✓ 📄 Added: Battery Degradation Study...
```

## Benefits

### 1. **Source Agnostic**
- Works with any CSV/Excel format
- No need to rename columns before import
- Automatic detection of source type

### 2. **Data Quality**
- Standardized field names internally
- CrossRef enrichment fills missing data
- Consistent structure for all papers

### 3. **Maintainability**
- Single source of truth for schema
- Easy to add new import sources
- Centralized mapping logic

### 4. **Flexibility**
- Falls back to generic mapping
- Handles case variations
- Works with partial data

## Adding New Import Sources

To support a new import source:

### 1. Add Detection Logic

```python
def detect_import_source(columns: list) -> str:
    columns_lower = [c.lower() for c in columns]

    # Add your detection logic
    if 'your_unique_column' in columns_lower:
        return 'your_source_name'

    # ... existing logic ...
```

### 2. Add Column Mapping

```python
IMPORT_SOURCE_MAPPINGS = {
    'your_source_name': {
        'SourceColumnName': 'canonical_field',
        'AnotherColumn': 'canonical_field',
        # ... more mappings ...
    },
    # ... existing mappings ...
}
```

### 3. Test Import

```python
# Test normalization
row = {'SourceColumnName': 'value'}
canonical = normalize_to_canonical_schema(row, 'your_source_name')
print(canonical)
```

## Example: Complete Import Flow

### Starting Data (Notion CSV)

```csv
Title,Authors / Orgs,Publication Year,URL
"Battery Study","Smith et al.",2024,"https://doi.org/10.1016/j.jpowsour.2024.123"
```

### Step 1: Detection

```
✓ Source: notion_csv
✓ Columns: Title, Authors / Orgs, Publication Year, URL
```

### Step 2: Normalization

```python
{
    'title': 'Battery Study',
    'authors': 'Smith et al.',
    'year': '2024',
    'url': 'https://doi.org/10.1016/j.jpowsour.2024.123',
    'doi': '',
    'journal': '',
    'abstract': '',
    # ... other fields empty ...
}
```

### Step 3: Enrichment

```
🔍 Extracting DOI from URL: 10.1016/j.jpowsour.2024.123
🔍 Querying CrossRef API...
✓ Found metadata:
  - Full title: "Battery Degradation Mechanisms in LFP Cells"
  - Authors: "John Smith, Jane Johnson, Bob Williams"
  - Journal: "Journal of Power Sources"
  - Abstract: "This paper investigates..."
```

### Step 4: Final Record

```python
{
    'title': 'Battery Degradation Mechanisms in LFP Cells',
    'authors': 'John Smith, Jane Johnson, Bob Williams',
    'year': '2024',
    'url': 'https://doi.org/10.1016/j.jpowsour.2024.123',
    'doi': '10.1016/j.jpowsour.2024.123',
    'journal': 'Journal of Power Sources',
    'abstract': 'This paper investigates...',
    'chemistry': '',
    'tags': '',
    'pdf_status': 'available',  # If PDF found
    'date_added': '2026-02-05T18:30:00',
    'notes': ''
}
```

## Error Handling

### Missing Required Fields

```python
if not canonical['title']:
    # Skip paper
    st.warning("⚠️ No title, skipping")
    continue
```

### CrossRef Enrichment Fails

```python
try:
    canonical = enrich_from_crossref(canonical)
except Exception:
    # Continue with original data
    pass
```

### Unknown Source Format

```python
# Falls back to generic mapping
source_type = detect_import_source(columns)  # Returns 'generic'
canonical = normalize_to_canonical_schema(row, 'generic')
```

## Future Enhancements (Step 4 from Plan)

### Manual Column Mapping UI

Allow users to map columns manually if auto-detection fails:

```python
# User interface:
Source Column        →  Canonical Field
─────────────────────────────────────
[Paper Title  ▼]    →  title
[Author List  ▼]    →  authors
[Pub Date     ▼]    →  year
[Journal Name ▼]    →  journal
```

**Features:**
- Dropdown for each canonical field
- Source column selection
- Save custom mappings
- Reuse for similar files

## Summary

The Canonical Import Schema provides:

✅ **Unified import** - Works with any source format
✅ **Auto-detection** - Recognizes Notion, Battery Datasets, generic
✅ **Normalization** - Converts to standard schema
✅ **Enrichment** - Fills missing fields via CrossRef
✅ **Extensible** - Easy to add new sources
✅ **Maintainable** - Single source of truth
✅ **User-friendly** - Shows mapping preview

**Status: PRODUCTION READY** 🎉

---

**Next Steps:**
1. ✅ Canonical schema defined
2. ✅ Source mappings created
3. ✅ Import logic updated
4. ⏳ Manual mapping UI (future enhancement)
