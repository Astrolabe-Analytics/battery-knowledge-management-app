"""
Papers API routes — CRUD operations for the paper library.

All data access goes through lib/db_operations.py (PostgreSQL).
"""
import time
import threading
from pathlib import Path
from typing import Optional, List
from collections import Counter

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
# Helpers
# ---------------------------------------------------------------------------

PAPERS_DIR = Path("papers")


def _get_paper_status(paper: dict) -> str:
    """Determine paper status from its dict representation."""
    filename = paper.get("filename", "")
    has_pdf = (PAPERS_DIR / filename).exists()

    title = (paper.get("title") or "").strip()
    has_title = bool(title) and "unknown" not in title.lower()
    # authors may be a semicolon-joined string from to_library_dict
    authors_raw = paper.get("authors", "")
    has_authors = bool(authors_raw) if isinstance(authors_raw, list) else bool(authors_raw and authors_raw.strip())
    has_year = bool(paper.get("year"))
    has_journal = bool(paper.get("journal"))
    metadata_complete = has_title and has_authors and has_year and has_journal

    if paper.get("ai_summary"):
        return "AI Summary"
    if has_pdf and paper.get("num_pages", 0) > 0:
        return "Complete" if metadata_complete else "Needs Metadata"
    if metadata_complete:
        return "Metadata Only"
    return "Incomplete"


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
        now = time.time()
        if not force_refresh and _papers_cache["data"] is not None and (now - _papers_cache["ts"]) < _CACHE_TTL:
            return _papers_cache["data"]

        from lib.db_operations import (
            get_paper_library,
            get_read_status,
            get_batch_paper_collections,
        )

        papers = get_paper_library()
        filenames = [p["filename"] for p in papers]

        # Batch read status
        read_statuses = get_read_status(filenames)

        # Batch collections (1 query instead of N)
        all_collections = get_batch_paper_collections(filenames)

        for paper in papers:
            fn = paper["filename"]
            paper["read"] = read_statuses.get(fn, False)
            paper["status"] = _get_paper_status(paper)
            paper["collections"] = [c for c in all_collections.get(fn, [])]

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
    """List papers with server-side filtering, sorting, and pagination."""
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
    """Return just the filenames of ALL papers matching the given filters."""
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
    from lib.db_operations import get_filter_options
    return get_filter_options()


@router.get("/stats")
def get_stats():
    """Get library statistics for sidebar display."""
    papers = _get_enriched_papers()

    total = len(papers)
    ai_summary = sum(1 for p in papers if p.get("status") == "AI Summary")
    complete = sum(1 for p in papers if p.get("status") == "Complete")
    metadata_only = sum(1 for p in papers if p.get("status") == "Metadata Only")
    incomplete = total - ai_summary - complete - metadata_only

    from lib.db_operations import get_collection_count
    chunk_count = get_collection_count()

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
    """Get distribution data for charts."""
    papers = _get_enriched_papers()

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


# ── Trash ────────────────────────────────────────────────

@router.get("/trash")
def list_trash():
    """List all soft-deleted papers."""
    from lib.db_operations import get_deleted_papers
    papers = get_deleted_papers()
    return {"papers": papers, "total": len(papers)}


@router.post("/trash/restore")
def restore_papers(body: DeleteRequest):
    """Restore soft-deleted papers (accepts same body as delete)."""
    from lib.db_operations import restore_paper
    results = []
    for filename in body.filenames:
        ok = restore_paper(filename)
        results.append({"filename": filename, "success": ok})
    invalidate_papers_cache()
    return {"results": results}


@router.delete("/trash")
def empty_trash():
    """Permanently delete all trashed papers."""
    from lib.db_operations import empty_trash as _empty_trash
    count = _empty_trash()
    invalidate_papers_cache()
    return {"success": True, "deleted": count}


@router.delete("/trash/{filename}")
def hard_delete_one(filename: str):
    """Permanently delete a single trashed paper."""
    from lib.db_operations import hard_delete_paper
    ok = hard_delete_paper(filename)
    if not ok:
        raise HTTPException(status_code=404, detail="Paper not found")
    invalidate_papers_cache()
    return {"success": True}


# ── Paper Detail ─────────────────────────────────────────

@router.get("/{filename}")
def get_paper(filename: str):
    """Get detailed information for a single paper."""
    from lib.db_operations import get_paper_details, get_read_status, get_paper_collections

    details = get_paper_details(filename)
    if not details:
        raise HTTPException(status_code=404, detail=f"Paper not found: {filename}")

    details["has_pdf"] = (PAPERS_DIR / filename).exists()

    # Notes (still file-based)
    notes_path = Path("data/notes") / f"{filename}.txt"
    details["notes"] = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""

    # Read status
    details["read"] = get_read_status([filename]).get(filename, False)

    # Collections
    details["collections"] = get_paper_collections(filename)

    return details


@router.patch("/{filename}/metadata")
def update_metadata(filename: str, body: MetadataUpdate):
    """Update metadata fields for a paper."""
    from lib.db_operations import update_paper_metadata_field

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    for key, value in updates.items():
        ok = update_paper_metadata_field(filename, key, value)
        if not ok:
            raise HTTPException(status_code=404, detail="Paper not found")

    invalidate_papers_cache()
    return {"success": True, "updated_fields": list(updates.keys())}


@router.put("/{filename}/notes")
def update_notes(filename: str, body: NoteUpdate):
    """Save or update notes for a paper."""
    from lib.db_operations import update_paper_metadata_field
    update_paper_metadata_field(filename, "notes", body.content)
    return {"success": True}


@router.get("/{filename}/notes")
def get_notes(filename: str):
    """Get notes for a paper."""
    from lib.db_operations import get_paper_details
    details = get_paper_details(filename)
    content = details.get("notes", "") if details else ""
    # Fallback to file-based notes for backward compat
    notes_path = Path("data/notes") / f"{filename}.txt"
    if not content and notes_path.exists():
        content = notes_path.read_text(encoding="utf-8")
    return {"content": content}


@router.put("/{filename}/read")
def set_read_status(filename: str, body: ReadStatusUpdate):
    """Set read/unread status for a paper."""
    from lib.db_operations import mark_as_read, mark_as_unread
    if body.read:
        mark_as_read(filename)
    else:
        mark_as_unread(filename)
    return {"success": True, "read": body.read}


@router.post("/{filename}/read/toggle")
def toggle_read(filename: str):
    """Toggle read status for a paper."""
    from lib.db_operations import toggle_read_status
    new_status = toggle_read_status(filename)
    invalidate_papers_cache()
    return {"success": True, "read": new_status}


@router.delete("")
def delete_papers(body: DeleteRequest):
    """Soft-delete one or more papers."""
    from lib.db_operations import delete_paper

    results = []
    for filename in body.filenames:
        ok = delete_paper(filename)
        results.append({"filename": filename, "success": ok})

    invalidate_papers_cache()
    return {"results": results}


@router.get("/{filename}/pdf")
def serve_pdf(filename: str):
    """Serve a paper's PDF file."""
    pdf_path = PAPERS_DIR / filename
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
    from lib.db_operations import get_paper_details

    details = get_paper_details(filename)
    if not details:
        raise HTTPException(status_code=404, detail="Paper not found")

    refs = details.get("references", [])

    # Cross-check which references are in library
    from lib.db_operations import get_paper_library

    def _norm_doi(d: str) -> str:
        d = d.lower().strip()
        for pfx in ('https://doi.org/', 'http://doi.org/', 'doi.org/', 'doi:'):
            if d.startswith(pfx): d = d[len(pfx):]
        return d

    def _norm_title(t: str) -> str:
        return ' '.join(t.lower().strip().split())

    library = get_paper_library()
    norm_library_dois = set()
    norm_library_titles = set()
    for p in library:
        d = p.get("doi", "")
        if d:
            norm_library_dois.add(_norm_doi(d))
        t = p.get("title", "")
        if t and len(t) > 10:
            norm_library_titles.add(_norm_title(t))

    for ref in refs:
        ref_doi = ref.get("DOI", "") or ref.get("doi", "")
        ref_title = ref.get("article-title", "") or ref.get("title", "")
        in_library = False

        if ref_doi and _norm_doi(ref_doi) in norm_library_dois:
            in_library = True
        elif ref_title and len(ref_title) > 10:
            in_library = _norm_title(ref_title) in norm_library_titles

        ref["in_library"] = in_library

    return {"references": refs, "total": len(refs)}
