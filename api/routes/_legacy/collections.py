"""
Collections API routes — CRUD for paper collections.

Wraps: lib/collections.py (all functions are pure backend, no Streamlit deps)
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
    from lib.collections import get_all_collections
    collections = get_all_collections()
    return {"collections": collections}


@router.post("")
def create_collection(body: CollectionCreate):
    """Create a new collection."""
    from lib.collections import create_collection
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
    from lib.collections import get_collection_by_id
    collection = get_collection_by_id(collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@router.patch("/{collection_id}")
def update_collection(collection_id: int, body: CollectionUpdate):
    """Update a collection's name, color, or description."""
    from lib.collections import update_collection
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = update_collection(collection_id, **updates)
    return result


@router.delete("/{collection_id}")
def delete_collection(collection_id: int):
    """Delete a collection (cascades to remove paper assignments)."""
    from lib.collections import delete_collection
    result = delete_collection(collection_id)
    return result


@router.post("/{collection_id}/papers")
def add_paper(collection_id: int, body: PaperAssignment):
    """Add a paper to a collection."""
    from lib.collections import add_paper_to_collection
    result = add_paper_to_collection(collection_id, body.filename)
    return result


@router.post("/{collection_id}/papers/bulk")
def add_papers_bulk(collection_id: int, body: BulkPaperAssignment):
    """Add multiple papers to a collection in one call.
    Uses a single DB connection + transaction for reliability."""
    import sqlite3
    from datetime import datetime
    from lib.collections import DB_PATH, _get_connection

    conn = _get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    added = 0
    skipped = 0

    for fn in body.filenames:
        try:
            cursor.execute(
                "INSERT INTO collection_items (collection_id, filename, added_date) VALUES (?, ?, ?)",
                (collection_id, fn, now)
            )
            added += 1
        except sqlite3.IntegrityError:
            skipped += 1  # already in collection
        except Exception:
            skipped += 1

    # Update collection modified_date once
    if added > 0:
        cursor.execute(
            "UPDATE collections SET modified_date = ? WHERE id = ?",
            (now, collection_id)
        )

    conn.commit()
    conn.close()
    return {"success": True, "added": added, "skipped": skipped, "total": len(body.filenames)}


@router.delete("/{collection_id}/papers/{filename}")
def remove_paper(collection_id: int, filename: str):
    """Remove a paper from a collection."""
    from lib.collections import remove_paper_from_collection
    result = remove_paper_from_collection(collection_id, filename)
    return result


@router.get("/{collection_id}/papers")
def list_collection_papers(collection_id: int):
    """Get all paper filenames in a collection."""
    from lib.collections import get_collection_papers
    filenames = get_collection_papers(collection_id)
    return {"filenames": filenames, "total": len(filenames)}
