"""
Discover API routes — Semantic Scholar search + Gap Analysis.

All data reads/writes go through PostgreSQL (lib/db_operations).
"""

import re
import logging
from typing import Optional
from datetime import datetime, timezone
from collections import defaultdict
from difflib import SequenceMatcher

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    query: str
    limit: int = 20
    sort: str = "relevance"  # "relevance" or "citationCount"


class AddPaperRequest(BaseModel):
    doi: str
    title: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[str] = None
    url: Optional[str] = None


# ---------------------------------------------------------------------------
# Discover / Semantic Scholar Search
# ---------------------------------------------------------------------------


@router.post("/search")
def search_semantic_scholar(body: SearchRequest):
    """
    Search Semantic Scholar for papers.
    Annotates results with 'in_library' flag.
    """
    from lib.semantic_scholar import (
        search_papers,
        format_paper_for_display,
        check_papers_in_library,
    )

    raw = search_papers(
        query=body.query,
        limit=body.limit,
        sort=body.sort,
    )

    if not raw.get("data"):
        return {"papers": [], "total": 0}

    papers = [format_paper_for_display(p) for p in raw["data"]]

    # Cross-check with library (Postgres)
    from lib.db_operations import get_library_dois_and_titles

    library_dois, library_titles = get_library_dois_and_titles()

    papers = check_papers_in_library(papers, library_dois, library_titles)

    return {"papers": papers, "total": len(papers)}


# ---------------------------------------------------------------------------
# Add paper to library (PostgreSQL)
# ---------------------------------------------------------------------------


def _query_crossref(doi: str) -> Optional[dict]:
    """Query CrossRef for metadata (same as imports helper)."""
    try:
        url = f"https://api.crossref.org/works/{doi}"
        headers = {"User-Agent": "AstrolabeLibrary/1.0 (mailto:researcher@example.com)"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        message = resp.json().get("message", {})

        metadata = {}
        titles = message.get("title", [])
        if titles:
            import re

            metadata["title"] = (
                re.sub(r"\s*\[[A-Z]\]\s*\.?\s*$", "", titles[0]).strip() or titles[0]
            )

        authors = []
        for a in message.get("author", []):
            given, family = a.get("given", ""), a.get("family", "")
            if family:
                authors.append(f"{family}, {given}" if given else family)
        metadata["authors"] = authors[:10]

        published = message.get("published-print") or message.get("published-online")
        if published and "date-parts" in published:
            parts = published["date-parts"][0]
            if parts:
                metadata["year"] = str(parts[0])

        metadata["journal"] = (
            message.get("container-title", [""])[0]
            if message.get("container-title")
            else ""
        )
        metadata["abstract"] = message.get("abstract", "")
        metadata["volume"] = message.get("volume", "")
        metadata["issue"] = message.get("issue", "")
        metadata["pages"] = message.get("page", "")
        metadata["author_keywords"] = []

        refs = []
        for ref in message.get("reference", [])[:100]:
            raw_ref_title = ref.get("article-title", "")
            clean_ref_title = (
                re.sub(r"\s*\[[A-Z]\]\s*\.?\s*$", "", raw_ref_title).strip()
                if raw_ref_title
                else ""
            )
            refs.append(
                {
                    "key": ref.get("key", ""),
                    "DOI": ref.get("DOI", ""),
                    "doi-asserted-by": ref.get("doi-asserted-by", ""),
                    "article-title": clean_ref_title,
                    "author": ref.get("author", ""),
                    "year": ref.get("year", ""),
                    "journal-title": ref.get("journal-title", ""),
                    "volume": ref.get("volume", ""),
                    "first-page": ref.get("first-page", ""),
                }
            )
        metadata["references"] = refs

        return metadata
    except Exception:
        return None


@router.post("/add")
def add_from_discover(body: AddPaperRequest):
    """
    Add a paper found via Semantic Scholar search to the library.
    Tries to find an open-access PDF; falls back to metadata-only.
    All data goes to PostgreSQL.
    """
    from lib.db_operations import upsert_paper, save_paper_references, add_chunks
    from lib.jats import strip_jats

    doi = body.doi
    title = body.title or ""
    authors_str = body.authors or ""
    year = body.year or ""
    url = body.url or ""

    try:
        # Step 1: CrossRef metadata
        crossref = _query_crossref(doi) if doi else None
        if not crossref:
            crossref = {
                "title": title,
                "authors": [authors_str] if authors_str else [],
                "year": year,
            }

        # Step 2: Try Semantic Scholar for OA PDF
        pdf_url = None
        pdf_found = False

        if doi:
            try:
                from lib.semantic_scholar import search_papers, format_paper_for_display

                raw = search_papers(query=f"doi:{doi}", limit=1)
                if raw.get("success") and raw.get("data"):
                    formatted = format_paper_for_display(raw["data"][0])
                    if formatted.get("is_open_access") and formatted.get("pdf_url"):
                        pdf_url = formatted["pdf_url"]
                        pdf_found = True
            except Exception:
                pass

        # Step 3: Unpaywall fallback
        if not pdf_found and doi:
            try:
                resp = requests.get(
                    f"https://api.unpaywall.org/v2/{doi}?email=researcher@example.com",
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("is_oa") and data.get("best_oa_location", {}).get(
                        "url_for_pdf"
                    ):
                        pdf_url = data["best_oa_location"]["url_for_pdf"]
                        pdf_found = True
            except Exception:
                pass

        # Step 4: Download PDF if found
        filename = None
        if pdf_found and pdf_url:
            try:
                from lib.semantic_scholar import download_pdf_bytes
                from lib.s3_storage import save_pdf

                safe_title = re.sub(r"[^\w\s-]", "", title[:50])
                safe_title = re.sub(r"[-\s]+", "_", safe_title)
                filename = f"{safe_title}.pdf"
                dl = download_pdf_bytes(pdf_url)
                if not dl.get("success"):
                    pdf_found = False
                    filename = None
                else:
                    save_pdf(filename, dl.get("content"))
            except Exception:
                pdf_found = False
                filename = None

        # Step 5: Determine filename
        if not filename:
            if doi:
                safe_doi = doi.replace("/", "_").replace(".", "_")
                filename = f"doi_{safe_doi}.pdf"
            else:
                safe_title = re.sub(r"[^\w\s-]", "", title[:50])
                safe_title = re.sub(r"[-\s]+", "_", safe_title)
                filename = f"{safe_title}.pdf"

        # Step 6: Normalize journal
        journal = crossref.get("journal", "")
        if journal:
            try:
                from lib.journal_normalizer import normalize_journal_name

                journal = normalize_journal_name(journal)
            except Exception:
                pass

        abstract = strip_jats(crossref.get("abstract", ""))

        # Step 7: Upsert into PostgreSQL
        upsert_paper(
            filename,
            {
                "title": crossref.get("title", title),
                "authors": crossref.get(
                    "authors", [authors_str] if authors_str else []
                ),
                "year": crossref.get("year", year),
                "journal": journal,
                "doi": doi,
                "abstract": abstract,
                "volume": crossref.get("volume", ""),
                "issue": crossref.get("issue", ""),
                "pages": crossref.get("pages", ""),
                "author_keywords": crossref.get("author_keywords", []),
                "chemistries": [],
                "topics": [],
                "application": "general",
                "paper_type": "Experimental",
                "metadata_only": not pdf_found,
                "pdf_status": "available" if pdf_found else "needs_pdf",
                "source_url": url,
                "notes": "",
                "date_added": datetime.now(timezone.utc),
            },
        )

        # Save references
        refs = crossref.get("references", [])
        if refs:
            save_paper_references(filename, refs)

        # Add metadata-only chunk for search visibility
        chunk_text = f"Metadata: {crossref.get('title', title)}. DOI: {doi}"
        if abstract:
            chunk_text += f"\n\nAbstract: {abstract}"

        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            embedding = model.encode(chunk_text).tolist()
        except Exception:
            embedding = None

        add_chunks(
            [
                {
                    "id": f"{filename}_metadata",
                    "paper_filename": filename,
                    "page_num": 0,
                    "chunk_index": 0,
                    "token_count": len(chunk_text.split()),
                    "section_name": "metadata",
                    "content": chunk_text,
                    "embedding": embedding,
                }
            ]
        )

        return {
            "success": True,
            "message": (
                f"Added: {title[:50]}..." if len(title) > 50 else f"Added: {title}"
            ),
            "pdf_found": pdf_found,
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to add {title[:30]}...: {str(e)}",
            "pdf_found": False,
        }


# ---------------------------------------------------------------------------
# Gap Analysis (PostgreSQL)
# ---------------------------------------------------------------------------


def _analyze_reference_gaps_pg(limit: int = 50) -> tuple[list[dict], dict]:
    """
    Analyze paper_references table to find frequently cited papers
    not in the library.  Returns (gaps_list, stats_dict).
    """
    from lib.db import get_session
    from lib.models import Paper, PaperReference

    with get_session() as session:
        # Build library DOI and title sets
        rows = (
            session.query(Paper.doi, Paper.title)
            .filter(Paper.deleted_at.is_(None))
            .all()
        )

        library_dois = {r.doi.lower() for r in rows if r.doi}
        library_titles = {r.title.lower().strip() for r in rows if r.title}

        # Load all references with their parent paper title
        refs = (
            session.query(
                PaperReference.doi,
                PaperReference.article_title,
                PaperReference.author,
                PaperReference.year,
                PaperReference.journal_title,
                PaperReference.paper_filename,
                Paper.title,
            )
            .join(Paper, Paper.filename == PaperReference.paper_filename)
            .filter(Paper.deleted_at.is_(None))
            .all()
        )

    # Aggregate
    aggregator = defaultdict(
        lambda: {
            "title": "",
            "authors": "",
            "year": "",
            "journal": "",
            "doi": "",
            "citation_count": 0,
            "cited_by": [],
            "_years": [],
        }
    )

    for ref in refs:
        ref_title = (ref.article_title or "").strip()
        ref_author = (ref.author or "").strip()
        if not ref_title or not ref_author:
            continue

        ref_doi = (ref.doi or "").lower().strip()
        for prefix in ["https://doi.org/", "http://doi.org/", "doi.org/", "doi:"]:
            if ref_doi.startswith(prefix):
                ref_doi = ref_doi[len(prefix) :]

        lookup_key = ref_doi if ref_doi else ref_title.lower().strip()
        if not lookup_key:
            continue

        # Check if in library (exact DOI or exact title match only — no
        # fuzzy matching, which is O(n*m) and too slow for 74K references)
        in_library = False
        if ref_doi and ref_doi in library_dois:
            in_library = True
        elif ref_title:
            norm = ref_title.lower().strip()
            if norm in library_titles:
                in_library = True
        if in_library:
            continue

        agg = aggregator[lookup_key]
        if not agg["title"] or len(ref_title) > len(agg["title"]):
            agg["title"] = ref_title
        if not agg["authors"] or len(ref_author) > len(agg["authors"]):
            agg["authors"] = ref_author
        if ref.year:
            try:
                y = int(ref.year)
                if 1800 <= y <= 2030:
                    agg["_years"].append(str(y))
            except (ValueError, TypeError):
                pass
        if ref.journal_title and (
            not agg["journal"] or len(ref.journal_title) > len(agg["journal"])
        ):
            agg["journal"] = ref.journal_title
        if ref_doi and not agg["doi"]:
            agg["doi"] = ref.doi or ""

        agg["citation_count"] += 1
        parent_title = ref.title or ref.paper_filename.replace(".pdf", "")
        if parent_title not in agg["cited_by"]:
            agg["cited_by"].append(parent_title)

    # Resolve year for each gap: use mode (most common), break ties with earliest
    for agg in aggregator.values():
        years = agg.pop("_years", [])
        if years:
            from collections import Counter as _Counter

            year_counts = _Counter(years)
            max_count = max(year_counts.values())
            most_common = [y for y, c in year_counts.items() if c == max_count]
            agg["year"] = min(most_common)  # earliest among most-common

    gaps = sorted(aggregator.values(), key=lambda x: x["citation_count"], reverse=True)

    total_citations = sum(g["citation_count"] for g in gaps)
    stats = {
        "total_gaps": len(gaps),
        "total_citations": total_citations,
        "avg_citations_per_gap": round(total_citations / len(gaps), 2) if gaps else 0.0,
        "top_gap_count": gaps[0]["citation_count"] if gaps else 0,
    }

    return gaps[:limit], stats


@router.get("/gaps")
def get_gaps(limit: int = 20):
    """
    Analyze references across all library papers to find frequently cited
    papers that are NOT in the library.  Reads from PostgreSQL.
    """
    gaps, stats = _analyze_reference_gaps_pg(limit=limit)
    return {"gaps": gaps, "stats": stats}


@router.post("/gaps/add")
def add_gap_paper(body: AddPaperRequest):
    """Add a gap-analysis paper to the library (same as /add)."""
    return add_from_discover(body)
