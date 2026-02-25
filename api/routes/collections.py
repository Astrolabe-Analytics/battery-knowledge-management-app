"""
Collections API routes — CRUD for paper collections.

All data access goes through lib/db_operations.py (PostgreSQL).
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CollectionCreate(BaseModel):
    name: str
    color: Optional[str] = None
    description: Optional[str] = None

class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None

class PaperAssignment(BaseModel):
    filename: str

class BulkPaperAssignment(BaseModel):
    filenames: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def list_collections():
    """Get all collections with paper counts."""
    from lib.db_operations import get_all_collections
    collections = get_all_collections()
    return {"collections": collections}


@router.post("")
def create_new_collection(body: CollectionCreate):
    """Create a new collection."""
    from lib.db_operations import create_collection
    result = create_collection(
        name=body.name,
        color=body.color,
        description=body.description,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Failed to create collection"))
    return result


@router.get("/{collection_id}")
def get_collection(collection_id: int):
    """Get a single collection by ID."""
    from lib.db_operations import get_collection_by_id
    collection = get_collection_by_id(collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@router.patch("/{collection_id}")
def update_collection(collection_id: int, body: CollectionUpdate):
    """Update a collection's name, color, or description."""
    from lib.db_operations import update_collection as db_update_collection
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = db_update_collection(collection_id, **updates)
    return result


@router.delete("/{collection_id}")
def remove_collection(collection_id: int):
    """Delete a collection (cascades to remove paper assignments)."""
    from lib.db_operations import delete_collection
    result = delete_collection(collection_id)
    return result


@router.post("/{collection_id}/papers")
def add_paper(collection_id: int, body: PaperAssignment):
    """Add a paper to a collection."""
    from lib.db_operations import add_paper_to_collection
    result = add_paper_to_collection(collection_id, body.filename)
    return result


@router.post("/{collection_id}/papers/bulk")
def add_papers_bulk(collection_id: int, body: BulkPaperAssignment):
    """Add multiple papers to a collection."""
    from lib.db_operations import add_paper_to_collection

    added = 0
    skipped = 0
    for fn in body.filenames:
        result = add_paper_to_collection(collection_id, fn)
        if result.get("success"):
            added += 1
        else:
            skipped += 1

    return {"success": True, "added": added, "skipped": skipped, "total": len(body.filenames)}


@router.delete("/{collection_id}/papers/{filename}")
def remove_paper(collection_id: int, filename: str):
    """Remove a paper from a collection."""
    from lib.db_operations import remove_paper_from_collection
    result = remove_paper_from_collection(collection_id, filename)
    return result


@router.get("/{collection_id}/papers")
def list_collection_papers(collection_id: int):
    """Get all paper filenames in a collection."""
    from lib.db_operations import get_collection_papers
    filenames = get_collection_papers(collection_id)
    return {"filenames": filenames, "total": len(filenames)}
