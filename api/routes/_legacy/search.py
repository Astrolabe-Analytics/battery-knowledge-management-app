"""
Search / RAG API routes — semantic search and question-answering.

Wraps: lib/rag.py (retrieve_relevant_chunks, retrieve_with_hybrid_and_reranking, query_claude)
"""
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    """Simple semantic search request."""
    query: str
    top_k: int = 5
    chemistry: Optional[str] = None
    topic: Optional[str] = None
    paper_type: Optional[str] = None
    collection_id: Optional[int] = None

class RAGRequest(BaseModel):
    """Full RAG pipeline request: expansion → hybrid search → reranking → answer."""
    question: str
    top_k: int = 5
    n_candidates: int = 15
    alpha: float = 0.5
    chemistry: Optional[str] = None
    topic: Optional[str] = None
    paper_type: Optional[str] = None
    collection_id: Optional[int] = None
    enable_query_expansion: bool = True
    enable_reranking: bool = True

class ChunkResult(BaseModel):
    filename: str
    page: int | str
    section: str
    text: str
    score: float = 0.0
    title: str = ""

class SearchResponse(BaseModel):
    chunks: list[dict]
    total: int

class RAGResponse(BaseModel):
    answer: str
    chunks: list[dict]
    question: str
    query_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/chunks", response_model=SearchResponse)
def search_chunks(body: SearchRequest):
    """
    Simple semantic search — returns relevant chunks without LLM answer.
    Useful for "find passages about X" without the full RAG pipeline.
    """
    from lib.rag import retrieve_relevant_chunks

    chunks = retrieve_relevant_chunks(
        question=body.query,
        top_k=body.top_k,
        filter_chemistry=body.chemistry,
        filter_topic=body.topic,
        filter_paper_type=body.paper_type,
    )

    return {"chunks": chunks, "total": len(chunks)}


@router.post("/ask", response_model=RAGResponse)
def ask_question(body: RAGRequest):
    """
    Full RAG pipeline: query expansion → hybrid search → reranking → Claude answer.
    This is the main research endpoint — equivalent to the Research page.
    """
    from lib.rag import (
        retrieve_with_hybrid_and_reranking,
        query_claude,
        get_api_key_from_env,
    )
    from lib.query_history import save_query

    api_key = get_api_key_from_env()
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY not set. Configure it in your .env file.",
        )

    # Get collection filenames if filtering by collection
    collection_filenames = None
    if body.collection_id:
        from lib.collections import get_collection_papers
        filenames = get_collection_papers(body.collection_id)
        collection_filenames = set(filenames) if filenames else None

    # Run the hybrid retrieval pipeline
    chunks = retrieve_with_hybrid_and_reranking(
        question=body.question,
        api_key=api_key,
        top_k=body.top_k,
        n_candidates=body.n_candidates,
        alpha=body.alpha,
        filter_chemistry=body.chemistry,
        filter_topic=body.topic,
        filter_paper_type=body.paper_type,
        filter_collection_filenames=collection_filenames,
        enable_query_expansion=body.enable_query_expansion,
        enable_reranking=body.enable_reranking,
    )

    if not chunks:
        return {
            "answer": "No relevant passages found for your question.",
            "chunks": [],
            "question": body.question,
        }

    # Generate answer with Claude
    answer = query_claude(body.question, chunks, api_key)

    # Save to query history
    filters = {}
    if body.chemistry:
        filters["chemistry"] = body.chemistry
    if body.topic:
        filters["topic"] = body.topic
    if body.paper_type:
        filters["paper_type"] = body.paper_type
    if body.collection_id:
        filters["collection_id"] = body.collection_id

    query_id = save_query(
        question=body.question,
        answer=answer,
        chunks=chunks,
        filters=filters if filters else None,
    )

    return {
        "answer": answer,
        "chunks": chunks,
        "question": body.question,
        "query_id": query_id,
    }
