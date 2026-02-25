"""
Papers API routes — CRUD operations for the paper library.

Wraps: lib/rag.py, lib/library_operations.py, lib/read_status.py,
       lib/cached_operations.py, lib/app_helpers.py
"""
import json
import time
import threading
import sqlite3
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class PaperSummary(BaseModel):
    filename: str
    title: str
    authors: str | list
    year: str
    journal: str
    doi: str
    chemistries: list[str]
    topics: list[str]
    application: str
    paper_type: str
    num_pages: int
    date_added: str = ""
    pdf_status: str = ""
    feed_blurb: str = ""
    ai_summary: str = ""
    author_keywords: list[str] = []
    read: bool = False
    status: str = ""
    collections: list[dict] = []

class PaperDetail(BaseModel):
    filename: str
    title: str
    authors: list[str]
    year: str
    journal: str
    doi: str
    chemistries: list[str]
    topics: list[str]
    application: str
    paper_type: str
    author_keywords: list[str] = []
    abstract: str = ""
    ai_summary: str = ""
    feed_blurb: str = ""
    notes: str = ""
    references: list[dict] = []
    preview_chunks: list[dict] = []
    has_pdf: bool = False
    date_added: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    source_url: str = ""

class MetadataUpdate(BaseModel):
    doi: Optional[str] = None
    title: Optional[str] = None
    year: Optional[str] = None
    journal: Optional[str] = None
    chemistries: Optional[list[str]] = None
    topics: Optional[list[str]] = None

class NoteUpdate(BaseModel):
    content: str

class ReadStatusUpdate(BaseModel):
    read: bool

class DeleteRequest(BaseModel):
    filenames: list[str]

# ---------------------------------------------------------------------------
# Helpers — bypass Streamlit caching
# ---------------------------------------------------------------------------

def _load_metadata_json() -> dict:
    """Load metadata.json without Streamlit cache."""
    metadata_file = Path("data/metadata.json")
    if not metadata_file.exists():
        return {}
    with open(metadata_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_paper_status(paper: dict, full_meta: dict | None = None) -> str:
    """Determine paper status from metadata.
    Accepts pre-loaded full_meta dict to avoid re-reading JSON per paper."""
    filename = paper.get("filename", "")
    has_pdf = Path("papers", filename).exists()

    if full_meta is None:
        full_meta = _load_metadata_json()
    meta = full_meta.get(filename, {})

    if meta.get("ai_summary"):
        return "AI Summary"
    if has_pdf and paper.get("num_pages", 0) > 0:
        return "Complete"
    # No PDF — check if we have meaningful metadata (title + authors + year + journal)
    title = (meta.get("title") or "").strip()
    has_title = bool(title) and "unknown" not in title.lower()
    has_authors = bool(meta.get("authors"))
    has_year = bool(meta.get("year"))
    has_journal = bool(meta.get("journal"))
    if has_title and has_authors and has_year and has_journal:
        return "Metadata Only"
    return "Incomplete"


def _get_all_paper_collections_batch() -> dict:
    """Load collection memberships for ALL papers in a single query.
    Returns {filename: [collection_dicts]}."""
    from lib.collections import DB_PATH
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ci.filename, c.id, c.name, c.color, c.description, ci.added_date
            FROM collection_items ci
            JOIN collections c ON c.id = ci.collection_id
            ORDER BY c.name
        """)
        result: dict[str, list] = {}
        for row in cursor.fetchall():
            fn = row["filename"]
            if fn not in result:
                result[fn] = []
            result[fn].append({
                "id": row["id"], "name": row["name"],
                "color": row["color"], "description": row["description"],
                "added_date": row["added_date"],
            })
        conn.close()
        return result
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# In-memory cache for enriched paper list (TTL = 30s)
# ---------------------------------------------------------------------------
_papers_cache: dict = {"data": None, "ts": 0}
_papers_cache_lock = threading.Lock()
_CACHE_TTL = 30  # seconds


def _get_enriched_papers(force_refresh: bool = False) -> list[dict]:
    """Return fully enriched paper list with caching."""
    now = time.time()
    if not force_refresh and _papers_cache["data"] is not None and (now - _papers_cache["ts"]) < _CACHE_TTL:
        return _papers_cache["data"]

    with _papers_cache_lock:
        # Double-check after acquiring lock
        now = time.time()
        if not force_refresh and _papers_cache["data"] is not None and (now - _papers_cache["ts"]) < _CACHE_TTL:
            return _papers_cache["data"]

        from lib.rag import get_paper_library as _get_paper_library_cached
        papers = _get_paper_library_cached.__wrapped__() if hasattr(_get_paper_library_cached, '__wrapped__') else _get_paper_library_cached()

        # Batch read status
        from lib.read_status import get_read_status
        filenames = [p["filename"] for p in papers]
        read_statuses = get_read_status(filenames)

        # Batch collections (1 query instead of N)
        all_collections = _get_all_paper_collections_batch()

        # Load metadata.json once for status computation
        full_meta = _load_metadata_json()

        for paper in papers:
            paper["read"] = read_statuses.get(paper["filename"], False)
            paper["status"] = _get_paper_status(paper, full_meta)
            paper["collections"] = all_collections.get(paper["filename"], [])

        _papers_cache["data"] = papers
        _papers_cache["ts"] = time.time()
        return papers


def invalidate_papers_cache():
    """Call after any mutation to papers data."""
    _papers_cache["data"] = None
    _papers_cache["ts"] = 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def list_papers(
    search: Optional[str] = Query(None, description="Text search across title, authors, journal, DOI, keywords"),
    chemistry: Optional[str] = Query(None),
    topic: Optional[str] = Query(None),
    paper_type: Optional[str] = Query(None),
    collection: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort: Optional[str] = Query("date_added", description="Sort field"),
    sort_dir: Optional[str] = Query("desc", description="asc or desc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    """
    List papers with server-side filtering, sorting, and pagination.
    Uses an in-memory cache (30s TTL) to avoid re-reading ChromaDB on every request.
    """
    papers = _get_enriched_papers()

    # Apply filters
    if search:
        q = search.lower()
        papers = [p for p in papers if any(
            q in str(p.get(field, "")).lower()
            for field in ["title", "authors", "journal", "doi", "author_keywords"]
        )]
    if chemistry:
        papers = [p for p in papers if chemistry in p.get("chemistries", [])]
    if topic:
        papers = [p for p in papers if topic in p.get("topics", [])]
    if paper_type:
        papers = [p for p in papers if p.get("paper_type") == paper_type]
    if status:
        papers = [p for p in papers if p.get("status") == status]
    if collection:
        papers = [p for p in papers if any(
            c.get("name") == collection for c in p.get("collections", [])
        )]

    # Sort
    reverse = sort_dir == "desc"
    papers.sort(key=lambda p: str(p.get(sort, "")).lower(), reverse=reverse)

    total = len(papers)

    # Paginate
    papers = papers[offset:offset + limit]

    return {"papers": papers, "total": total, "offset": offset, "limit": limit}


@router.get("/filenames")
def list_filenames(
    search: Optional[str] = Query(None),
    chemistry: Optional[str] = Query(None),
    topic: Optional[str] = Query(None),
    paper_type: Optional[str] = Query(None),
    collection: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """
    Return just the filenames of ALL papers matching the given filters
    (no pagination). Useful for "select all results" bulk operations.
    """
    papers = _get_enriched_papers()

    if search:
        q = search.lower()
        papers = [p for p in papers if any(
            q in str(p.get(field, "")).lower()
            for field in ["title", "authors", "journal", "doi", "author_keywords"]
        )]
    if chemistry:
        papers = [p for p in papers if chemistry in p.get("chemistries", [])]
    if topic:
        papers = [p for p in papers if topic in p.get("topics", [])]
    if paper_type:
        papers = [p for p in papers if p.get("paper_type") == paper_type]
    if status:
        papers = [p for p in papers if p.get("status") == status]
    if collection:
        papers = [p for p in papers if any(
            c.get("name") == collection for c in p.get("collections", [])
        )]

    filenames = [p["filename"] for p in papers]
    return {"filenames": filenames, "total": len(filenames)}


@router.get("/filters")
def get_filters():
    """Get unique filter values for the filter bar."""
    from lib.rag import get_filter_options as _get_filter_options_cached

    fn = _get_filter_options_cached
    options = fn.__wrapped__() if hasattr(fn, "__wrapped__") else fn()
    return options


@router.get("/stats")
def get_stats():
    """Get library statistics for sidebar display."""
    papers = _get_enriched_papers()
    full_meta = _load_metadata_json()

    total = len(papers)
    ai_summary = sum(1 for p in papers if p.get("status") == "AI Summary")
    complete = sum(1 for p in papers if p.get("status") == "Complete")
    metadata_only = sum(1 for p in papers if p.get("status") == "Metadata Only")
    incomplete = total - ai_summary - complete - metadata_only

    from lib.rag import get_collection_count as _gcc
    gcc = _gcc.__wrapped__ if hasattr(_gcc, "__wrapped__") else _gcc
    chunk_count = gcc()

    return {
        "total_papers": total,
        "ai_summary": ai_summary,
        "complete": complete,
        "metadata_only": metadata_only,
        "incomplete": incomplete,
        "chunk_count": chunk_count,
    }


@router.get("/stats/charts")
def get_chart_data():
    """Get distribution data for charts (chemistry, topic, year, type)."""
    papers = _get_enriched_papers()
    from collections import Counter

    chem_counter = Counter()
    topic_counter = Counter()
    year_counter = Counter()
    type_counter = Counter()
    read_counter = Counter()

    for p in papers:
        for c in (p.get("chemistries") or []):
            chem_counter[c] += 1
        for t in (p.get("topics") or []):
            topic_counter[t] += 1
        yr = p.get("year")
        if yr:
            year_counter[str(yr)] += 1
        pt = p.get("paper_type")
        if pt:
            type_counter[pt] += 1
        read_counter["Read" if p.get("read") else "Unread"] += 1

    def top_n(counter, n=15):
        return [{"name": k, "count": v} for k, v in counter.most_common(n)]

    year_data = [{"name": k, "count": v} for k, v in sorted(year_counter.items())]

    return {
        "by_chemistry": top_n(chem_counter),
        "by_topic": top_n(topic_counter),
        "by_year": year_data,
        "by_type": top_n(type_counter, 10),
        "by_read_status": top_n(read_counter),
    }


@router.get("/{filename}")
def get_paper(filename: str):
    """Get detailed information for a single paper."""
    from lib.rag import get_paper_details, check_pdf_exists

    details = get_paper_details(filename)
    if not details:
        raise HTTPException(status_code=404, detail=f"Paper not found: {filename}")

    # Enrich with metadata.json fields
    full_meta = _load_metadata_json()
    meta = full_meta.get(filename, {})
    details["abstract"] = meta.get("abstract", "")
    details["ai_summary"] = meta.get("ai_summary", "")
    details["feed_blurb"] = meta.get("feed_blurb", "")
    details["references"] = meta.get("references", [])
    details["volume"] = meta.get("volume", "")
    details["issue"] = meta.get("issue", "")
    details["pages"] = meta.get("pages", "")
    details["source_url"] = meta.get("source_url", "")
    details["date_added"] = meta.get("date_added", "")
    details["has_pdf"] = check_pdf_exists(filename)

    # Notes
    notes_path = Path("data/notes") / f"{filename}.txt"
    details["notes"] = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""

    # Read status
    from lib.read_status import get_read_status
    details["read"] = get_read_status([filename]).get(filename, False)

    # Collections
    from lib.collections import get_paper_collections
    details["collections"] = get_paper_collections(filename)

    return details


@router.patch("/{filename}/metadata")
def update_metadata(filename: str, body: MetadataUpdate):
    """Update metadata fields for a paper."""
    from lib.app_helpers import update_paper_metadata

    full_meta = _load_metadata_json()
    if filename not in full_meta:
        raise HTTPException(status_code=404, detail="Paper not found")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Apply updates to metadata.json
    for key, value in updates.items():
        full_meta[filename][key] = value

    with open(Path("data/metadata.json"), "w", encoding="utf-8") as f:
        json.dump(full_meta, f, indent=2, ensure_ascii=False)

    # Sync to ChromaDB
    from lib.rag import DatabaseClient
    DatabaseClient.update_paper_metadata(filename, updates)

    invalidate_papers_cache()
    return {"success": True, "updated_fields": list(updates.keys())}


@router.put("/{filename}/notes")
def update_notes(filename: str, body: NoteUpdate):
    """Save or update notes for a paper."""
    notes_dir = Path("data/notes")
    notes_dir.mkdir(parents=True, exist_ok=True)
    notes_path = notes_dir / f"{filename}.txt"
    notes_path.write_text(body.content, encoding="utf-8")
    return {"success": True}


@router.get("/{filename}/notes")
def get_notes(filename: str):
    """Get notes for a paper."""
    notes_path = Path("data/notes") / f"{filename}.txt"
    content = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
    return {"content": content}


@router.put("/{filename}/read")
def set_read_status(filename: str, body: ReadStatusUpdate):
    """Set read/unread status for a paper."""
    from lib.read_status import mark_as_read, mark_as_unread
    if body.read:
        mark_as_read(filename)
    else:
        mark_as_unread(filename)
    return {"success": True, "read": body.read}


@router.post("/{filename}/read/toggle")
def toggle_read(filename: str):
    """Toggle read status for a paper."""
    from lib.read_status import toggle_read_status
    new_status = toggle_read_status(filename)
    invalidate_papers_cache()
    return {"success": True, "read": new_status}


@router.delete("")
def delete_papers(body: DeleteRequest):
    """Soft-delete one or more papers."""
    from lib.library_operations import soft_delete_paper

    results = []
    for filename in body.filenames:
        result = soft_delete_paper(filename)
        results.append({"filename": filename, **result})

    invalidate_papers_cache()
    return {"results": results}


@router.get("/{filename}/pdf")
def serve_pdf(filename: str):
    """Serve a paper's PDF file."""
    pdf_path = Path("papers") / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline",
    )


@router.get("/{filename}/references")
def get_references(filename: str):
    """Get references for a paper."""
    full_meta = _load_metadata_json()
    meta = full_meta.get(filename)
    if not meta:
        raise HTTPException(status_code=404, detail="Paper not found")

    refs = meta.get("references", [])

    # Cross-check which references are in library
    from lib.gap_analysis import normalize_doi, normalize_title

    # Pre-compute normalized library DOIs and titles for O(1) lookup
    norm_library_dois = set()
    norm_library_titles = set()
    for m in full_meta.values():
        d = m.get("doi", "")
        if d:
            norm_library_dois.add(normalize_doi(d))
        t = m.get("title", "")
        if t and len(t) > 10:
            norm_library_titles.add(normalize_title(t))

    for ref in refs:
        # Crossref uses uppercase "DOI"; some imports may use lowercase
        ref_doi = ref.get("DOI", "") or ref.get("doi", "")
        ref_title = ref.get("article-title", "") or ref.get("title", "")
        in_library = False

        if ref_doi and normalize_doi(ref_doi) in norm_library_dois:
            in_library = True
        elif ref_title and len(ref_title) > 10:
            in_library = normalize_title(ref_title) in norm_library_titles

        ref["in_library"] = in_library

    return {"references": refs, "total": len(refs)}
