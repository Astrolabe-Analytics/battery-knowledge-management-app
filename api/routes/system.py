"""
System API routes — cross-system integration endpoints.

These endpoints serve data to other Astrolabe systems (data-viz tool,
contribution pipeline). All data access goes through lib/db_operations.py.
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class PaperDiscoveryRequest(BaseModel):
    """Semantic paper discovery request (Tier 2 integration)."""
    query: str
    chemistries: list[str] = []
    top_k: int = 10


class PaperDiscoveryResult(BaseModel):
    paperId: str
    doi: str
    title: str
    abstract: str
    authors: list
    year: int | str
    journal: str
    chemistries: list[str]
    topics: list[str]
    relevanceScore: float
    matchReason: str  # structured: "semantic:cosine-0.87"


class PaperDiscoveryResponse(BaseModel):
    papers: list[dict]
    query: str
    total: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/paper-library")
def get_paper_library():
    """Return the full paper library for cross-system consumers.

    Format: array of paper objects with paperId, doi, title, abstract, etc.
    Consumer: data-viz-tool's paper-linker.mjs normalizes this to an array.
    """
    from lib.db_operations import get_paper_library_for_export
    return get_paper_library_for_export()


@router.post("/paper-library/search", response_model=PaperDiscoveryResponse)
def search_papers(body: PaperDiscoveryRequest):
    """Semantic paper discovery — find papers relevant to a dataset description.

    Tier 2 integration: the contribution tool sends a dataset description
    and gets back papers that study similar phenomena, matched by pgvector
    cosine similarity against embedded paper chunks.

    matchReason is structured: "semantic:cosine-0.87" (not free text).
    The consumer stamps source label and applies confidence cap on their side.

    URL pattern (production): https://knowledge.astrolabe-analytics.com/api/system/paper-library/search
    """
    from lib.db_operations import search_papers_semantic

    results = search_papers_semantic(
        query=body.query,
        top_k=body.top_k,
        chemistries=body.chemistries if body.chemistries else None,
    )

    return {
        "papers": results,
        "query": body.query,
        "total": len(results),
    }
