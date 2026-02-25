# Astrolabe CSV Import — Migration Reference Guide
## Everything We Learned the Hard Way (So the React Build Doesn't Repeat It)

---

## 1. Data Sources & Their Quirks

### Notion CSV Export (`_all.csv`, ~1,634 papers)
- **Format**: Nested zip (zip inside a zip) containing two CSVs; the big one ends in `_all.csv`
- **What's actually in it**: Title, URL, Tags — and *almost nothing else*. Authors, Year, Journal, Abstract are nearly all empty
- **Column headers**: Use capital letters (`Title`, `URL`, `Tags`, `Authors / Orgs`, `Publication Year`, etc.) — case-insensitive mapping is mandatory
- **Key lesson**: The URL field is the real gold. Nearly every entry has one, and that's the gateway to DOI extraction → CrossRef enrichment → full metadata

### Battery Datasets Catalog (Excel, 334 entries)
- **Format**: `.xlsx` with multiple sheets; main sheet is `Battery_Datasets`
- **What's actually in it**: title, paper_url, chemistry, journal, authors, tags, data URLs, code URLs — richer than Notion but still has gaps
- **Column headers**: Lowercase (`title`, `paper_url`, `chemistry`, `authors`, `journal`, `tags`)
- **No DOIs directly** — must extract from `paper_url`
- **Other useful sheets**: `Code_Repositories` (62 GitHub repos), `Other_Coverage` (44 excluded entries), `Astrolabe_Confidential` (13 restricted sources)

### Key Insight
Every import source has different column names for the same data. You **must** define a canonical schema and map each source to it.

---

## 2. Canonical Metadata Schema

This is the single internal representation all imports must map to:

```
title          — Paper title (required)
authors        — "Last, First; Last, First" format
year           — 4-digit integer
journal        — Full journal name (normalized — see section 7)
doi            — "10.xxxx/..." format
url            — Original source URL
abstract       — Paper abstract text
chemistry      — Normalized chemistry tags (see section 8)
topics         — AI-generated topic tags (SOH, RUL, degradation, EIS, etc.)
tags           — Original tags from import source
paper_type     — experimental | simulation | review | dataset | modeling
application    — EV | grid storage | consumer electronics | aviation | etc.
volume         — Journal volume
issue          — Journal issue
pages          — Page range
pdf_status     — has_pdf | metadata_only | needs_pdf
pdf_path       — Local path to PDF if available
source_url     — URL from original import (preserved separately from enriched URL)
date_added     — ISO datetime of when paper entered library
notes          — User-editable free text
author_keywords — Keywords from the paper itself (separate from AI-generated tags)
```

### Column Mapping Per Source

```python
COLUMN_MAPS = {
    "notion": {
        "Title": "title",
        "Authors / Orgs": "authors",
        "Publication Year": "year",
        "Journal": "journal",
        "URL": "url",
        "Tags": "tags",
        "Abstract/Notes": "abstract",
        "Data Link": "data_url",
        "Code": "code_url",
    },
    "battery_datasets_catalog": {
        "title": "title",
        "authors": "authors",
        "year": "year",
        "journal": "journal",
        "paper_url": "url",
        "chemistry": "chemistry",
        "tags": "tags",
    },
    "generic": {
        # Fallback: attempt case-insensitive matching
        # on common field names (title, author, doi, url, year, journal)
    }
}
```

**Implementation rules:**
1. Column mapping MUST be case-insensitive
2. For any fields not in the source, leave empty (not null — empty string)
3. After import, run enrichment pipeline to fill gaps
4. Future: let user manually map columns in UI for unknown CSV formats

---

## 3. DOI Extraction from URLs

This was one of the biggest pain points. Most publisher URLs contain DOIs, but each publisher formats them differently.

### Direct Extraction Patterns (Regex)

These publishers embed the DOI in the URL path:

```python
DOI_URL_PATTERNS = {
    "nature.com":       r"nature\.com/articles/(s\d+\-\d+\-\d+\-\w+)",
    # → DOI: 10.1038/{captured_group}

    "iopscience.iop.org": r"iopscience\.iop\.org/article/(10\.\d{4,}/[^\s?#]+)",
    # → DOI directly in URL

    "wiley.com":        r"onlinelibrary\.wiley\.com/doi/(10\.\d{4,}/[^\s?#]+)",
    # → DOI directly in URL

    "springer.com":     r"link\.springer\.com/article/(10\.\d{4,}/[^\s?#]+)",
    # → DOI directly in URL

    "mdpi.com":         r"mdpi\.com/(\d{4}-\d{4}/\d+/\d+/\d+)",
    # → DOI: 10.3390/{captured_path}

    "doi.org":          r"doi\.org/(10\.\d{4,}/[^\s?#]+)",
    # → DOI directly in URL

    "generic":          r"(10\.\d{4,}/[^\s?#]+)",
    # → Catch-all: any URL containing a DOI pattern starting with "10."
}
```

### URLs That CANNOT Be Parsed Directly

**ScienceDirect / Cell Press / Elsevier** use PII identifiers, not DOIs:
- `sciencedirect.com/science/article/pii/S0378775324011406`
- `cell.com/joule/fulltext/S2542-4351(24)00510-5`

PII → DOI conversion requires either the Elsevier API (needs key) or a fallback lookup. **Use Semantic Scholar title search as fallback** — this is the pragmatic solution.

### DOI Extraction Pipeline (Waterfall)

```
For each paper:
1. Try regex DOI extraction from URL
   ↓ (if fails)
2. Try Semantic Scholar title search → get DOI
   ↓ (if fails)
3. Try CrossRef title search → get DOI
   ↓ (if all fail)
4. Mark as "needs_doi" for manual resolution
```

**Impact**: Direct DOI extraction from URLs reduces Semantic Scholar API calls by 70-80%, which is critical for staying under rate limits.

---

## 4. Metadata Enrichment Pipeline

Once you have a DOI, you can get everything from CrossRef.

### Enrichment Waterfall

```
For each paper missing metadata:
1. If has DOI → query CrossRef API (https://api.crossref.org/works/{DOI})
2. If has URL but no DOI → extract DOI from URL (see section 3) → CrossRef
3. If only has title → Semantic Scholar title search → get DOI → CrossRef
4. For open access PDF discovery: query Unpaywall (https://api.unpaywall.org/v2/{doi}?email=you@email.com)
```

### API Details & Rate Limits

| API | Rate Limit (No Key) | Rate Limit (With Key) | Delay Between Calls |
|-----|---------------------|----------------------|-------------------|
| CrossRef | ~50 req/sec (polite pool) | Same | 1 second (be polite) |
| Semantic Scholar | 100 req/5 min | 1,000 req/5 min | 1 second minimum |
| Unpaywall | 100,000/day | Same | 1 second |

**Critical**: The Semantic Scholar API key (`x-api-key` header) is essential for batch operations. Without it, you'll hit 429 errors constantly during large imports.

### CrossRef Response Mapping

```python
def map_crossref_to_canonical(crossref_data):
    return {
        "title": crossref_data["title"][0],
        "authors": "; ".join(
            f"{a.get('family', '')}, {a.get('given', '')}"
            for a in crossref_data.get("author", [])
        ),
        "year": crossref_data.get("published-print", {})
                .get("date-parts", [[None]])[0][0]
                or crossref_data.get("published-online", {})
                .get("date-parts", [[None]])[0][0],
        "journal": crossref_data.get("container-title", [""])[0],
        "doi": crossref_data.get("DOI", ""),
        "abstract": crossref_data.get("abstract", ""),  # may contain HTML tags — strip them!
        "volume": crossref_data.get("volume", ""),
        "issue": crossref_data.get("issue", ""),
        "pages": crossref_data.get("page", ""),
    }
```

**Watch out for**: CrossRef abstracts sometimes contain HTML/JATS XML tags — strip them during mapping.

---

## 5. Duplicate Detection

This caused repeated headaches. Here's what actually works:

### Two-Layer Detection

```python
def is_duplicate(new_paper, existing_library):
    # Layer 1: DOI exact match (case-insensitive, strip URL prefix)
    if new_paper.get("doi"):
        clean_doi = new_paper["doi"].lower().replace("https://doi.org/", "").replace("http://doi.org/", "")
        for existing in existing_library:
            existing_doi = existing.get("doi", "").lower().replace("https://doi.org/", "").replace("http://doi.org/", "")
            if clean_doi == existing_doi:
                return True

    # Layer 2: Title similarity (>90% word overlap)
    if new_paper.get("title"):
        normalized_new = normalize_title(new_paper["title"])
        for existing in existing_library:
            normalized_existing = normalize_title(existing.get("title", ""))
            if title_similarity(normalized_new, normalized_existing) > 0.9:
                return True

    return False
```

### Title Normalization (THIS IS CRITICAL)

The #1 reason duplicate detection failed was subtle title differences:

```python
def normalize_title(title):
    """Normalize title for comparison.
    
    Issues we hit:
    - Leading/trailing whitespace
    - Different Unicode dashes (em-dash vs en-dash vs hyphen)
    - Curly vs straight quotes
    - Encoding artifacts
    - Truncation differences between sources
    - Extra spaces between words
    """
    if not title:
        return ""
    title = title.lower().strip()
    title = title.replace("\u2013", "-")  # en-dash → hyphen
    title = title.replace("\u2014", "-")  # em-dash → hyphen
    title = title.replace("\u2018", "'").replace("\u2019", "'")  # curly quotes
    title = title.replace("\u201c", '"').replace("\u201d", '"')
    title = re.sub(r'\s+', ' ', title)  # collapse multiple spaces
    title = re.sub(r'[^\w\s]', '', title)  # remove all punctuation
    return title
```

### Bugs We Hit
1. **Only 1 of 10 duplicates detected**: Title stored in DB had different whitespace than title in CSV
2. **DOI format mismatch**: One source stored `10.1234/abc` while another stored `https://doi.org/10.1234/abc` — normalize by stripping the URL prefix
3. **Title truncation**: One source truncated at 100 chars, creating a mismatch

---

## 6. Import Pipeline Architecture

### Save After Every Paper (Not Per Batch)

The import must persist each paper individually so crashes don't lose progress:

```
For each paper in CSV:
  1. Check duplicate → skip if exists
  2. Map columns to canonical schema
  3. Extract DOI from URL (if URL present)
  4. Fetch metadata from CrossRef (if DOI found)
  5. Search Semantic Scholar by title (if no DOI)
  6. Check Unpaywall for open-access PDF (if DOI found)
  7. Save to database ← COMMIT HERE, every single paper
  8. Update progress bar
```

### Batch Size Is Cosmetic

If you save after every paper, batching is just for UI progress display. The user should be able to click "Import All" and walk away — it loops through everything automatically.

### The ChromaDB / Metadata Sync Bug

**Root cause**: Papers were saved to `metadata.json` but NOT to ChromaDB. The library page read from ChromaDB, so imported papers were invisible.

**The fix**: Every save operation must write to BOTH stores. On startup, run a sync check.

**React migration**: Use a single database (Postgres + pgvector) to eliminate this class of bug entirely.

### Stats Must Derive From Table Data

Library stats (Complete / Metadata Only / Incomplete) were calculated separately from the table data, causing them to be out of sync. **Fix**: Compute stats from the same query/DataFrame that populates the table. Never maintain a separate counter.

---

## 7. Journal Name Normalization

Different sources use different journal name formats. Normalize on import:

```python
JOURNAL_NORMALIZATIONS = {
    "j power sources": "Journal of Power Sources",
    "journal of power sources": "Journal of Power Sources",
    "j. power sources": "Journal of Power Sources",
    "j electrochem soc": "Journal of The Electrochemical Society",
    "electrochimica acta": "Electrochimica Acta",
    "j energy storage": "Journal of Energy Storage",
    "j. energy storage": "Journal of Energy Storage",
    "appl energy": "Applied Energy",
    "applied energy": "Applied Energy",
    "energy environ sci": "Energy & Environmental Science",
    "nat energy": "Nature Energy",
    # ... extend as needed
}
```

**Approach**: Lowercase + strip punctuation for lookup, store the canonical full name.

---

## 8. Chemistry Taxonomy & Normalization

Map all variants to canonical names during import:

```python
CHEMISTRY_TAXONOMY = {
    # Canonical → [all known variants]
    "LFP":     ["LFP", "LiFePO4", "LiFePO 4", "lithium iron phosphate", "lifepo4"],
    "NMC":     ["NMC", "Li(NiMnCo)O2", "nickel manganese cobalt"],
    "NMC111":  ["NMC111", "NMC333"],
    "NMC532":  ["NMC532"],
    "NMC622":  ["NMC622"],
    "NMC811":  ["NMC811"],
    "NCA":     ["NCA", "LiNiCoAlO2", "nickel cobalt aluminum"],
    "LCO":     ["LCO", "LiCoO2", "lithium cobalt oxide"],
    "LTO":     ["LTO", "Li4Ti5O12", "lithium titanate"],
    "Li-ion":  ["Li-ion", "lithium-ion", "lithium ion", "Li ion"],
    "LMO":     ["LMO", "LiMn2O4", "lithium manganese oxide"],
}
```

**NMC variant rule**: Tag with BOTH the specific variant (NMC811) AND the parent (NMC). Filtering by "NMC" returns all variants; filtering by "NMC811" returns only that specific one.

---

## 9. UI/UX Lessons (Carry Forward to React)

### Progress Display
- Progress bar + short status line: `"Enriching paper 2 of 10: A decade of insights..."`
- Summary at end: `"✅ Enriched 5 papers. ⚠️ 3 failed (rate limited). ⏭️ 2 skipped."`
- Detailed logs hidden by default behind expandable section

### DOI Editing
- Must persist to the database immediately on save
- Must invalidate all caches / refetch after save
- Add a "Find DOI" button that searches Semantic Scholar by title and auto-fills

### Enrichment Button
- "Enrich Metadata" finds papers with URLs but missing metadata
- Should also check Unpaywall for PDFs when it finds a DOI
- Must actually update the display after running (cache invalidation!)

### Error Handling
- Every API call needs try/except with meaningful error messages
- Failed enrichments should log the specific failure reason (no DOI found? CrossRef error? rate limited?)
- Never show raw KeyErrors to the user — check for key existence before access

---

## 10. Known Bugs to Fix in React

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| DOI edits don't persist after refresh | Save not writing to both stores + stale cache | Single DB + proper cache invalidation |
| Library stats out of sync | Stats computed separately from table data | Derive stats from same data source |
| Delete selected does nothing | Confirm button handler not wired up | Wire it up properly |
| ChromaDB / metadata.json desync | Dual-write not atomic | Single database (Postgres + pgvector) |
| Enrichment says "success" but nothing changes | Wrote to metadata.json but not ChromaDB | Single database |
| URL stored in title field | Notion export data quality issue | Validate on import: if "title" starts with http, it's a URL — extract real title from the page |

---

## 11. Architecture Recommendations for React Migration

### Eliminate the Dual-Store Problem
The biggest source of bugs was `metadata.json` + ChromaDB being out of sync. **Use Postgres + pgvector as a single source of truth.** One database, one write path, no sync issues.

### API-First Design
Build FastAPI endpoints for every operation:

```
POST   /api/papers/import/csv     — Upload and process CSV
POST   /api/papers/import/url     — Import single paper by URL
POST   /api/papers/enrich         — Batch enrich metadata
GET    /api/papers                — List papers (with filters, pagination)
GET    /api/papers/{id}           — Paper detail
PATCH  /api/papers/{id}           — Update paper metadata (DOI edit, etc.)
DELETE /api/papers/{id}           — Delete paper
POST   /api/search                — RAG search
GET    /api/stats                 — Library statistics (derived from papers table)
```

### Background Jobs for Long Operations
CSV import of 1,600 papers should be a background job, not blocking the UI. Use Celery or a simple async task queue, with WebSocket or polling for progress updates. Jobs are resumable (skip already-imported papers).

### Validation Layer
Add input validation that the Streamlit version lacked:
- If "title" starts with `http`, it's probably a URL in the wrong field
- DOIs must match `10.\d{4,}/` pattern
- Year must be 4-digit integer between 1950 and current year + 1
- Reject empty titles
- Reject duplicate entries at the API level

---

## 12. API Keys & Environment

| Service | Key Required? | Env Variable | Notes |
|---------|--------------|-------------|-------|
| CrossRef | No (but add `mailto` header) | `CROSSREF_EMAIL` | Puts you in "polite pool" for better rate limits |
| Semantic Scholar | Yes (for batch work) | `SEMANTIC_SCHOLAR_API_KEY` | 10x rate limit improvement |
| Unpaywall | No (just needs email) | `UNPAYWALL_EMAIL` | Same email as CrossRef is fine |
| Claude API | Yes | `ANTHROPIC_API_KEY` | For RAG queries and auto-tagging |
| OpenAI | Optional | `OPENAI_API_KEY` | For embeddings if using text-embedding-3-small |

---

## 13. Import Testing Checklist

Before declaring the import pipeline "done" in React, verify all of these:

- [ ] Notion CSV imports with correct column mapping (case-insensitive)
- [ ] Battery Datasets Excel imports with correct column mapping
- [ ] Generic CSV with unknown columns prompts for manual mapping
- [ ] DOIs extracted from Nature, MDPI, IOP, Wiley, Springer URLs
- [ ] ScienceDirect/Cell URLs fall back to Semantic Scholar title search
- [ ] CrossRef enrichment populates authors, year, journal, abstract, volume, issue
- [ ] Unpaywall finds open-access PDFs when available
- [ ] Duplicate detection catches DOI matches (case-insensitive, strip URL prefix)
- [ ] Duplicate detection catches title matches (normalized, >90% similarity)
- [ ] Each paper saved individually (not batched) for crash resilience
- [ ] Re-running same import skips all previously imported papers
- [ ] Progress display shows bar + status + summary (details hidden by default)
- [ ] Stats update immediately after import/enrichment
- [ ] Chemistry tags normalized to canonical taxonomy
- [ ] Journal names normalized to full canonical form
- [ ] Papers with URL-in-title-field are caught and corrected
- [ ] All API calls have try/except with meaningful error messages
- [ ] Rate limits respected for all external APIs
- [ ] Single database — no dual-store sync issues
