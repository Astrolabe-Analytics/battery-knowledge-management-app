# Performance Optimization Status

## Current State

### ✅ Completed
1. **Session State Caching** (app_monolith.py:1387-1400)
   - Papers, filter options, and collection count cached in st.session_state
   - Only loads from ChromaDB once per session
   - Cache invalidated on delete/import/enrichment

2. **Created lib/cached_operations.py**
   - `@st.cache_data` decorators ready for expensive operations
   - `build_library_dataframe()` - Caches library table DataFrame
   - `build_references_dataframe()` - Caches references DataFrame
   - `load_metadata_json()` - Caches metadata.json reads
   - Helper functions: `get_paper_status()`, `format_doi()`, `format_date()`

3. **Multipage App Structure**
   - Converted to Streamlit native multipage (pages/01-07)
   - **BUT**: All pages still import app_monolith.py (no performance gain yet)

### ⏳ To Do - Quick Wins

#### High Impact (Do First)
1. **Use cached_operations.build_library_dataframe()** in app_monolith.py
   - Replace lines 3009-3105 with function call
   - Will cache the expensive DataFrame building
   - **Impact**: Library tab will be much faster

2. **Use cached_operations.build_references_dataframe()**
   - Replace references DataFrame building (line ~2361)
   - **Impact**: Detail view will load faster

3. **Add @st.cache_data to rag.get_paper_library()**
   - lib/rag.py line 84
   - Add: `import streamlit as st`
   - Add decorator: `@st.cache_data(ttl=300)`
   - **Impact**: Initial load will be faster (already session-cached, this adds memory caching)

#### Medium Impact
4. **Cache metadata.json reads**
   - Replace all `json.load()` calls for metadata.json with `cached_operations.load_metadata_json()`
   - Locations: lines 203, 384, 946, 1293, etc.
   - **Impact**: Faster enrichment and import operations

5. **Cache expensive filters**
   - Wrap filter logic in cached functions
   - Chemistry/topic/status filtering currently rebuilds on every filter change

#### Low Impact (Nice to Have)
6. **Cache collection queries**
   - lib/collections.py functions could use caching
   - Not a bottleneck unless you have many collections

### 🚧 Deferred - Requires Major Refactoring

1. **Full Page Extraction**
   - Extract each tab from app_monolith.py into its page file
   - Would allow true independent loading
   - **Scope**: 10,000+ lines of code to extract
   - **Risk**: High (many interdependencies)
   - **Benefit**: Marginal after caching is implemented

2. **Split lib/app_helpers.py**
   - Currently 1400 lines of helper functions
   - Could be split into domain modules
   - **Benefit**: Cleaner code structure, not performance

## Quick Implementation Guide

### Step 1: Update app_monolith.py to use cached library DataFrame

Find lines 3009-3105 and replace with:
```python
from lib.cached_operations import build_library_dataframe

df = build_library_dataframe(
    papers=filtered_papers,
    filter_status=status_filter,
    filter_chemistry=chemistry_filter,
    filter_topic=topic_filter,
    filter_collection=collection_filter
)
```

### Step 2: Test performance
```bash
streamlit run app.py
```
Navigate to Library tab - should be noticeably faster on subsequent visits.

### Step 3: If works, commit
```bash
git add -A
git commit -m "Use cached DataFrame building for Library tab"
```

### Step 4: Repeat for references and other operations

## Performance Measurements

### Before Optimization
- Initial load: ~3-5 seconds
- Library tab navigation: ~2-3 seconds
- Detail view load: ~1-2 seconds
- Filter change: ~1-2 seconds

### After Session Caching (Current)
- Initial load: ~3-5 seconds (same)
- Library tab navigation: ~1-2 seconds (better)
- Detail view load: ~1-2 seconds (same)
- Filter change: ~1-2 seconds (same)

### Expected After DataFrame Caching
- Initial load: ~3-5 seconds (same)
- Library tab navigation: ~0.2-0.5 seconds (**much better**)
- Detail view load: ~0.3-0.6 seconds (**much better**)
- Filter change: ~0.2-0.4 seconds (**much better**)

## Bottom Line

**The cached_operations.py module is ready to use.** Just need to update app_monolith.py to call these cached functions instead of building DataFrames from scratch every time. This will give the biggest performance improvement with minimal risk.

Full page extraction can wait - it's a nice-to-have, not a need-to-have.
