# Astrolabe — Development Lessons Learned
## Hard-Won Patterns for Working with Claude Code & Avoiding Past Mistakes

---

## 1. Working with Claude Code

### It Will Claim Things Are Fixed Without Testing

Claude Code often reports "✅ Fixed!" based on reading the code, not running it. It will describe what it changed and why it should work — but it didn't actually verify.

**Always end prompts with:** "Test it yourself before telling me it's done."

For UI bugs specifically: "Load the page, click the button, and confirm the behavior changed."

### It Does Fake Refactors

When asked to break up a 6,000-line monolith into a multipage app, Claude Code:
1. Renamed `app.py` to `app_monolith.py`
2. Created a 16-line `app.py` that imported `app_monolith`
3. Reported "✅ Converted to multipage app!"

All 6,000 lines still executed on every page load. No performance improvement at all.

**Always verify structural changes actually changed the structure.** Ask: "Does this page still import or execute app_monolith in any way? Show me the import chain."

### It Tries to Do Too Much at Once

When given two bugs in one prompt, Claude Code often conflates them or half-fixes both. One focused task per prompt produces much better results.

**Bad:** "Fix duplicate detection AND enrichment stats not updating."
**Good:** "Fix duplicate detection. Don't touch anything else."

### It Leaves Debug Artifacts Everywhere

Claude Code adds `print("[DEBUG]...")`, `st.write("DEBUG: ...")`, timing statements, and test code — then never cleans them up. After a few sessions you'll have dozens of debug prints polluting the console and UI.

**After every fix session:** "Remove all debug statements, test prints, and timing code. Commit the cleanup."

### It Suggests Overly Complex Solutions

When a simple fix would work, Claude Code sometimes proposes elaborate architectures. For example, when asked to fix a broken AG Grid table, it rewrote the entire CSS system instead of checking if the data was actually being passed to the component.

**Start simple:** "Before rewriting anything, add a `st.write(df)` right before the component to check if the data exists."

### The "Find and Fix" Pattern Works Best

Instead of relaying error messages back and forth, let Claude Code investigate:

```
The enrichment failed for all 4 papers with no useful error details. 
Add detailed logging to show exactly why each one failed — is it 
failing to extract a DOI? Is CrossRef returning an error? 

Test it on the first paper and show me step by step: what URL it has, 
what DOI it extracts, what CrossRef returns, and where it fails.
```

This gives Claude Code the full debugging loop instead of making you the middleman.

### It Forgets Context Across Long Sessions

After 20+ back-and-forth messages, Claude Code starts losing track of what was already fixed, what the current state of the code is, and what the original goal was. It may re-introduce bugs it already fixed or propose changes that conflict with earlier work.

**For long sessions:** Periodically commit to git and summarize the current state. If things get messy, start a fresh Claude Code session with a clear prompt describing where you are.

### Verify Imports After Refactoring

After any file reorganization, Claude Code frequently leaves broken imports — referencing modules that don't exist, importing from the old monolith, or creating circular dependencies.

**After any refactor:** "Check every file for import errors. Run `python -c 'import pages.library'` for each module and fix any ImportErrors before telling me it's done."

---

## 2. Streamlit Architecture Traps

### Every Interaction Reruns the Entire Script

This is Streamlit's fundamental design. Clicking a checkbox, pressing a button, changing a filter — all of it reruns your entire Python file from top to bottom. This is why:
- The page "greys out" briefly on every click
- A 6,000-line file makes everything slow
- You can't have truly independent components

**Mitigation:** Break into Streamlit's native multipage app structure (separate files in `pages/` directory). Each page only runs when navigated to. Use `@st.cache_data` aggressively for expensive operations.

**Real fix:** Move to React. This problem doesn't exist in a normal web framework.

### AG Grid Component Conflicts

AG Grid (via `streamlit-aggrid`) breaks when multiple instances exist across different Streamlit pages. The library table worked perfectly, but a second AG Grid on the detail page rendered as a blank dark box — and no amount of CSS or config changes could fix it.

**The AG Grid references table was never fixed.** We eventually had to remove it entirely.

**Lesson for React:** Use a proper table component (like TanStack Table / React Table) that doesn't have singleton instance limitations.

### Session State Variables Leak Into DataFrames

Streamlit session state keys can accidentally appear as DataFrame columns if you're not careful about how you construct DataFrames from session data. We had a "navigate_trigger" column appear in the library table because a session state variable bled into the data.

**Always explicitly select columns** when building DataFrames for display, rather than passing raw data objects that might contain extra keys.

### Cache Invalidation Is Manual

`@st.cache_data` won't know that you just imported 50 papers or enriched metadata. You must explicitly clear the cache after any mutation:

```python
# After import/enrichment/delete/edit:
st.cache_data.clear()  # Nuclear option — clears everything
# Or use cache keys and clear specific ones
```

Without this, the UI will show stale data after every write operation. This was the root cause of "enrichment says success but stats don't change."

### The Monolith Problem

A single large Python file (ours hit 5,944 lines) means Streamlit parses and evaluates ALL of it on every interaction, even for tabs you're not viewing. The fix was extracting each page into its own file in the `pages/` directory, with shared logic in a `lib/` folder.

**Key insight:** The extraction must be real. Each page file should import only what it needs from `lib/`, never the monolith. If any page has `import app_monolith` or `from app_monolith import *`, the performance is identical to before.

**Performance after proper extraction:**
- Before: 3-5 second page loads (parsing 6,000 lines every time)
- After: <0.5 seconds for Library tab (parsing ~500 lines + cached data)

---

## 3. Data Integrity Patterns

### Single Source of Truth (The #1 Lesson)

The Streamlit app used two data stores: `metadata.json` (flat file) and ChromaDB (vector DB). They constantly got out of sync:
- Papers saved to metadata.json but not ChromaDB → invisible in library
- Enrichment updated metadata.json but not ChromaDB → stale search results
- Library stats read from one store, table from another → wrong counts

**In the React build: use ONE database (Postgres + pgvector).** One write path. One read path. No sync bugs.

### DOI Link Double-Prefixing

When constructing DOI URLs, the code added `https://doi.org/` to DOIs that already had the prefix, producing `https://doi.org/https://doi.org/10.1234/abc`.

**Always strip existing prefixes before adding one:**
```python
def doi_to_url(doi):
    clean = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    return f"https://doi.org/{clean}"
```

### CrossRef Abstract HTML Tags

CrossRef API responses sometimes return abstracts with raw HTML or JATS XML tags (`<p>`, `<jats:p>`, etc.). These render as literal text in the UI if not stripped.

**Strip HTML from CrossRef abstracts on import:**
```python
import re
def clean_abstract(abstract):
    return re.sub(r'<[^>]+>', '', abstract).strip()
```

### URL-in-Title-Field Problem

Some Notion export rows had URLs where the title should be. This happens when the Notion database entry was just a bookmark with no title filled in.

**Validate on import:**
```python
if title and title.startswith(("http://", "https://")):
    # This is a URL, not a title
    url = title
    title = ""  # Mark for enrichment, or scrape the page for the real title
```

### Field Name Inconsistency Across the Codebase

Different parts of the code used different names for the same field:
- `chemistry_tags` vs `chemistries` vs `chemistry`
- `source_url` vs `url` vs `paper_url`

This caused subtle bugs where one function wrote to `chemistry` but another read from `chemistries` and found nothing.

**In the React build:** Define the schema ONCE (as a Pydantic model or SQLAlchemy model) and use it everywhere. No ad-hoc dictionaries with inconsistent keys.

---

## 4. API Integration Patterns

### Rate Limiting Is Not Optional

Without proper delays between API calls, batch operations (importing 100+ papers) will hit 429 errors from Semantic Scholar within minutes. The unauthenticated limit is 100 requests per 5 minutes — that's about 1 request every 3 seconds.

**Always add delays, even with an API key.** 1 second between CrossRef calls, 1 second between Semantic Scholar calls. It feels slow but it's the difference between processing 1,600 papers overnight vs. crashing at paper 50.

### Semantic Scholar API Key Is Essential

Without it: 100 requests / 5 minutes (will fail during any batch operation)
With it: 1,000 requests / 5 minutes (10x headroom)

The key is free — just apply at semanticscholar.org. Pass it as the `x-api-key` header.

### Waterfall Lookup Pattern

Don't try one API and give up. Chain them:

```
DOI extraction from URL → CrossRef lookup
    ↓ (if fails)
Semantic Scholar title search → get DOI → CrossRef
    ↓ (if fails)
CrossRef title search → get DOI
    ↓ (if all fail)
Mark as "needs_doi" for manual resolution
```

Each fallback level catches papers the previous one missed. The waterfall reduced our "unknown DOI" rate from ~60% to ~15%.

### Never Trust API Response Structure

CrossRef, Semantic Scholar, and Unpaywall all return slightly different response shapes depending on the paper. Fields that exist for one paper may be missing for another.

**Always use `.get()` with defaults:**
```python
# Bad
year = response["published-print"]["date-parts"][0][0]

# Good
year = (response.get("published-print", {})
        .get("date-parts", [[None]])[0][0]
        or response.get("published-online", {})
        .get("date-parts", [[None]])[0][0])
```

---

## 5. Process Lessons

### Git Commit Before Every Experiment

Before telling Claude Code to try something risky (refactor, new feature, architectural change), commit what you have:

```bash
git add -A && git commit -m "checkpoint before refactor attempt"
```

This saved us multiple times when a refactor broke everything and we needed to revert.

### Don't Mix Feature Work and Refactoring

Several sessions went poorly because we tried to fix bugs, add features, AND refactor the codebase all at once. Changes interacted in unexpected ways.

**Dedicated sessions for:** bug fixes, new features, refactoring, performance optimization. Don't mix them.

### The "Code Health Check" Pattern

After multiple incremental patches, the codebase accumulates dead code, duplicate logic, and leftover debug statements. Periodically ask Claude Code:

```
Before we add anything else, do a code quality review:
1. How many lines is the main file?
2. Find and remove all debug statements
3. Find duplicate functions or logic
4. Find dead code (unused functions/imports)
5. Give me a diagnosis — what's the overall state?
```

### Test the Happy Path AND the Repeat Path

A common pattern: import works the first time but breaks on re-run (duplicates not detected, caches not cleared, state not reset). Always test:
1. Does it work the first time? (Happy path)
2. Does it work if I do it again immediately? (Idempotency)
3. Does it work after refreshing the page? (Persistence)

---

## 6. What Carries Over to React (and What Doesn't)

### Carries Over (Backend Logic)
- DOI extraction patterns and waterfall lookup
- CrossRef / Semantic Scholar / Unpaywall API integration
- Duplicate detection with title normalization
- Chemistry and journal normalization taxonomies
- Canonical metadata schema
- RAG pipeline (chunking, embedding, retrieval, reranking)
- PDF parsing with pymupdf4llm

### Gets Thrown Away (Streamlit-Specific)
- All `st.cache_data` decorators and session state management
- AG Grid configuration and custom CSS
- Sidebar layout and tab structure
- The multipage `pages/` directory structure
- Any Streamlit component workarounds

### Gets Rebuilt Better (Architecture)
- `metadata.json` + ChromaDB → Postgres + pgvector (single store)
- Synchronous import blocking the UI → background job queue
- Stats as separate calculation → derived from the same query
- Ad-hoc dict schemas → Pydantic models / SQLAlchemy ORM
