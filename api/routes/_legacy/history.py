"""
History API routes — query history CRUD.

Wraps: lib/query_history.py (all pure backend, no Streamlit deps)
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class StarToggle(BaseModel):
    starred: Optional[bool] = None  # If None, toggle; if set, force value


@router.get("")
def list_queries(
    limit: Optional[int] = None,
    starred_only: bool = False,
):
    """Get query history, optionally filtered."""
    from lib.query_history import get_all_queries, get_starred_queries

    if starred_only:
        queries = get_starred_queries()
    else:
        queries = get_all_queries(limit=limit)

    return {"queries": queries, "total": len(queries)}


@router.get("/{query_id}")
def get_query(query_id: int):
    """Get a specific query by ID."""
    from lib.query_history import get_query_by_id
    query = get_query_by_id(query_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")
    return query


@router.post("/{query_id}/star")
def toggle_star(query_id: int):
    """Toggle starred status for a query."""
    from lib.query_history import toggle_star
    new_status = toggle_star(query_id)
    return {"success": True, "starred": new_status}


@router.delete("/{query_id}")
def delete_query(query_id: int):
    """Delete a specific query from history."""
    from lib.query_history import delete_query
    success = delete_query(query_id)
    if not success:
        raise HTTPException(status_code=404, detail="Query not found")
    return {"success": True}


@router.delete("")
def clear_history():
    """Delete all query history."""
    from lib.query_history import clear_all_history
    count = clear_all_history()
    return {"success": True, "deleted_count": count}
