"""
Search / RAG API routes — semantic search and question-answering.

All data access goes through lib/db_operations.py (PostgreSQL).
LLM calls still go through lib/rag.py (Claude API, query expansion, reranking).
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
    """Simple semantic search — returns relevant chunks without LLM answer."""
    from lib.db_operations import retrieve_relevant_chunks

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
    """Full RAG pipeline: query expansion → hybrid search → reranking → Claude answer."""
    from lib.llm import (
        query_claude,
        get_api_key_from_env,
        expand_query,
        rerank_chunks,
    )
    from lib.db_operations import hybrid_search, get_collection_papers, save_query

    api_key = get_api_key_from_env()
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY not set. Configure it in your .env file.",
        )

    # Get collection filenames if filtering by collection
    collection_filenames = None
    if body.collection_id:
        filenames = get_collection_papers(body.collection_id)
        collection_filenames = set(filenames) if filenames else None

    # Step 1: Query expansion
    search_query = body.question
    if body.enable_query_expansion and api_key:
        try:
            search_query = expand_query(body.question, api_key)
        except Exception:
            search_query = body.question

    # Step 2: Hybrid search from Postgres
    candidates = hybrid_search(
        query=search_query,
        top_k=body.n_candidates,
        alpha=body.alpha,
        filter_chemistry=body.chemistry,
        filter_topic=body.topic,
        filter_paper_type=body.paper_type,
        filter_collection_filenames=collection_filenames,
    )

    if not candidates:
        return {
            "answer": "No relevant passages found for your question.",
            "chunks": [],
            "question": body.question,
        }

    # Step 3: Reranking (still uses Claude)
    if body.enable_reranking and api_key and len(candidates) > body.top_k:
        chunks = rerank_chunks(
            query=body.question,
            chunks=candidates,
            api_key=api_key,
            top_k=body.top_k,
        )
    else:
        chunks = candidates[:body.top_k]

    # Step 4: Generate answer with Claude
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
