"""
Database operations module — PostgreSQL-backed replacements for
metadata.json / ChromaDB / SQLite data access.

Every public function here is a drop-in replacement for the corresponding
function in lib/rag.py, lib/collections.py, lib/read_status.py, or
lib/query_history.py.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from sqlalchemy import func, select, delete, update, and_, or_, text
from sqlalchemy.orm import Session, selectinload

from .db import get_session, engine
from .models import (
    Paper,
    PaperReference,
    Chunk,
    Collection,
    CollectionItem,
    QueryHistory,
    Setting,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_list(val) -> list:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [x.strip() for x in val.replace(";", ",").split(",") if x.strip()]
    return []


def _utcnow():
    return datetime.now(timezone.utc)


# ═════════════════════════════════════════════════════════════════════════════
# PAPER LIBRARY  (replaces rag.get_paper_library, get_filter_options, etc.)
# ═════════════════════════════════════════════════════════════════════════════

def get_paper_library() -> list[dict]:
    """Return every non-deleted paper in library-list format.

    This replaces the old `rag.get_paper_library()` which merged ChromaDB
    metadata with metadata.json.  Now it's just a single Postgres query.
    """
    with get_session() as session:
        # Get papers and their chunk counts in one query
        stmt = (
            select(
                Paper,
                func.count(Chunk.id).label("chunk_count"),
            )
            .outerjoin(Chunk, Chunk.paper_filename == Paper.filename)
            .where(Paper.deleted_at.is_(None))
            .group_by(Paper.filename)
        )
        rows = session.execute(stmt).all()

        papers = []
        for paper, chunk_count in rows:
            d = paper.to_library_dict()
            d["num_pages"] = chunk_count  # close enough (≈ one chunk per page)
            papers.append(d)

    return papers


def get_filter_options() -> dict:
    """Unique values for the filter dropdowns.

    Returns dict with keys: chemistries, topics, paper_types
    """
    with get_session() as session:
        rows = session.execute(
            select(Paper.chemistries, Paper.topics, Paper.paper_type)
            .where(Paper.deleted_at.is_(None))
        ).all()

    chemistries: set[str] = set()
    topics: set[str] = set()
    paper_types: set[str] = set()

    for chems, tops, pt in rows:
        for c in _ensure_list(chems):
            if c and len(c) >= 2:
                chemistries.add(c)
        for t in _ensure_list(tops):
            if t and len(t) >= 2:
                topics.add(t)
        if pt and pt.strip():
            paper_types.add(pt.strip())

    return {
        "chemistries": sorted(chemistries),
        "topics": sorted(topics),
        "paper_types": sorted(paper_types),
    }


def get_paper_details(filename: str) -> Optional[dict]:
    """Full detail view for a single paper (detail page)."""
    with get_session() as session:
        paper = session.get(Paper, filename)
        if paper is None or paper.deleted_at is not None:
            return None

        # Preview chunks (first 3)
        chunks = (
            session.execute(
                select(Chunk)
                .where(Chunk.paper_filename == filename)
                .order_by(Chunk.page_num, Chunk.chunk_index)
                .limit(3)
            )
            .scalars()
            .all()
        )

        details = paper.to_detail_dict()
        details["preview_chunks"] = [
            {"page": c.page_num, "text": c.content} for c in chunks
        ]
        return details


def get_paper_by_filename(filename: str) -> Optional[Paper]:
    """Raw ORM object for internal use."""
    with get_session() as session:
        return session.get(Paper, filename)


# ═════════════════════════════════════════════════════════════════════════════
# PAPER MUTATIONS
# ═════════════════════════════════════════════════════════════════════════════

def upsert_paper(filename: str, data: dict) -> Paper:
    """Insert or update a paper. `data` is a flat dict of column values."""
    with get_session() as session:
        paper = session.get(Paper, filename)
        if paper is None:
            paper = Paper(filename=filename)
            session.add(paper)

        for key, value in data.items():
            if hasattr(paper, key) and key != "filename":
                setattr(paper, key, value)

        session.flush()
        # Detach so it's usable outside session
        session.expunge(paper)
        return paper


def delete_paper(filename: str) -> bool:
    """Soft-delete a paper by setting deleted_at."""
    with get_session() as session:
        paper = session.get(Paper, filename)
        if paper is None:
            return False
        paper.deleted_at = _utcnow()
        return True


def hard_delete_paper(filename: str) -> bool:
    """Permanently delete a paper and all related data."""
    with get_session() as session:
        paper = session.get(Paper, filename)
        if paper is None:
            return False
        session.delete(paper)
        return True


def restore_paper(filename: str) -> bool:
    """Restore a soft-deleted paper by clearing deleted_at."""
    with get_session() as session:
        paper = session.get(Paper, filename)
        if paper is None or paper.deleted_at is None:
            return False
        paper.deleted_at = None
        return True


def get_deleted_papers() -> list[dict]:
    """Return all soft-deleted papers (the trash)."""
    with get_session() as session:
        rows = session.execute(
            select(Paper)
            .where(Paper.deleted_at.isnot(None))
            .order_by(Paper.deleted_at.desc())
        ).scalars().all()
        results = []
        for paper in rows:
            d = paper.to_library_dict()
            d["deleted_at"] = paper.deleted_at.isoformat() if paper.deleted_at else ""
            results.append(d)
        return results


def empty_trash() -> int:
    """Permanently delete all soft-deleted papers. Returns count."""
    with get_session() as session:
        trashed = session.execute(
            select(Paper).where(Paper.deleted_at.isnot(None))
        ).scalars().all()
        count = len(trashed)
        for paper in trashed:
            session.delete(paper)
        return count


def update_paper_metadata_field(filename: str, field: str, value) -> bool:
    """Update a single metadata field on a paper."""
    with get_session() as session:
        paper = session.get(Paper, filename)
        if paper is None:
            return False
        if not hasattr(paper, field):
            return False
        setattr(paper, field, value)
        return True


def save_paper_references(filename: str, references: list[dict]):
    """Replace all references for a paper."""
    with get_session() as session:
        session.execute(
            delete(PaperReference).where(PaperReference.paper_filename == filename)
        )
        for ref in references:
            if not isinstance(ref, dict):
                continue
            session.add(PaperReference(
                paper_filename=filename,
                ref_key=ref.get("key", ""),
                doi=ref.get("DOI", ""),
                doi_asserted_by=ref.get("doi-asserted-by", ""),
                article_title=ref.get("article-title", ""),
                author=ref.get("author", ""),
                year=ref.get("year", ""),
                journal_title=ref.get("journal-title", ""),
                volume=ref.get("volume", ""),
                first_page=ref.get("first-page", ""),
            ))


# ═════════════════════════════════════════════════════════════════════════════
# CHUNKS / VECTOR SEARCH  (replaces ChromaDB)
# ═════════════════════════════════════════════════════════════════════════════

def add_chunks(chunks_data: list[dict]):
    """Bulk-insert chunks (used by the ingest pipeline).

    Each dict in chunks_data should have:
      id, paper_filename, page_num, chunk_index, token_count,
      section_name, content, embedding (list[float] | None)
    """
    with get_session() as session:
        for cd in chunks_data:
            session.add(Chunk(
                id=cd["id"],
                paper_filename=cd["paper_filename"],
                page_num=cd.get("page_num", 0),
                chunk_index=cd.get("chunk_index", 0),
                token_count=cd.get("token_count", 0),
                section_name=cd.get("section_name", "Content"),
                content=cd["content"],
                embedding=cd.get("embedding"),
            ))
        session.flush()


def delete_chunks_for_paper(filename: str) -> int:
    """Delete all chunks for a paper. Returns count deleted."""
    with get_session() as session:
        result = session.execute(
            delete(Chunk).where(Chunk.paper_filename == filename)
        )
        return result.rowcount


def get_collection_count() -> int:
    """Total number of chunks in the database."""
    with get_session() as session:
        return session.execute(select(func.count(Chunk.id))).scalar() or 0


def retrieve_relevant_chunks(
    question: str,
    top_k: int = 5,
    filter_chemistry: Optional[str] = None,
    filter_topic: Optional[str] = None,
    filter_paper_type: Optional[str] = None,
) -> list[dict]:
    """Pure vector (cosine) similarity search over chunks.

    Uses pgvector <=> operator when available, otherwise falls back to
    numpy-based cosine similarity.
    """
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    query_embedding = model.encode([question])[0]

    return _vector_search(
        query_embedding=query_embedding,
        top_k=top_k,
        filter_chemistry=filter_chemistry,
        filter_topic=filter_topic,
        filter_paper_type=filter_paper_type,
    )


def _vector_search(
    query_embedding: np.ndarray,
    top_k: int = 5,
    filter_chemistry: Optional[str] = None,
    filter_topic: Optional[str] = None,
    filter_paper_type: Optional[str] = None,
    filter_collection_filenames: Optional[set] = None,
) -> list[dict]:
    """Low-level vector search.  Tries pgvector, falls back to numpy."""
    try:
        return _vector_search_pgvector(
            query_embedding, top_k,
            filter_chemistry, filter_topic, filter_paper_type,
            filter_collection_filenames,
        )
    except Exception:
        return _vector_search_numpy(
            query_embedding, top_k,
            filter_chemistry, filter_topic, filter_paper_type,
            filter_collection_filenames,
        )


def _vector_search_pgvector(
    query_embedding: np.ndarray,
    top_k: int,
    filter_chemistry: Optional[str],
    filter_topic: Optional[str],
    filter_paper_type: Optional[str],
    filter_collection_filenames: Optional[set],
) -> list[dict]:
    """Use pgvector's <=> (cosine distance) operator for search."""
    emb_list = query_embedding.tolist()

    with get_session() as session:
        # Build base query with cosine distance
        q = (
            select(
                Chunk,
                Chunk.embedding.cosine_distance(emb_list).label("distance"),
            )
            .join(Paper, Paper.filename == Chunk.paper_filename)
            .where(Paper.deleted_at.is_(None))
            .where(Chunk.embedding.isnot(None))
        )

        # Apply filters via paper join
        if filter_paper_type:
            q = q.where(Paper.paper_type == filter_paper_type)
        if filter_collection_filenames:
            q = q.where(Paper.filename.in_(filter_collection_filenames))
        # Chemistry & topic filters use JSONB containment
        if filter_chemistry:
            q = q.where(Paper.chemistries.contains([filter_chemistry.upper()]))
        if filter_topic:
            q = q.where(Paper.topics.contains([filter_topic.lower()]))

        q = q.order_by("distance").limit(top_k)
        rows = session.execute(q).all()

        return [_chunk_to_dict(chunk, 1.0 - dist) for chunk, dist in rows]


def _vector_search_numpy(
    query_embedding: np.ndarray,
    top_k: int,
    filter_chemistry: Optional[str],
    filter_topic: Optional[str],
    filter_paper_type: Optional[str],
    filter_collection_filenames: Optional[set],
) -> list[dict]:
    """Fallback: load embeddings into numpy and compute cosine similarity."""
    with get_session() as session:
        q = (
            select(Chunk, Paper)
            .join(Paper, Paper.filename == Chunk.paper_filename)
            .where(Paper.deleted_at.is_(None))
            .where(Chunk.embedding.isnot(None))
        )
        if filter_paper_type:
            q = q.where(Paper.paper_type == filter_paper_type)
        if filter_collection_filenames:
            q = q.where(Paper.filename.in_(filter_collection_filenames))

        rows = session.execute(q).all()

    # Post-filter chemistry/topic (JSONB containment may not work without pgvector)
    filtered: list[tuple] = []
    for chunk, paper in rows:
        if filter_chemistry:
            chems = [c.upper() for c in _ensure_list(paper.chemistries)]
            if filter_chemistry.upper() not in chems:
                continue
        if filter_topic:
            tops = [t.lower() for t in _ensure_list(paper.topics)]
            if filter_topic.lower() not in tops:
                continue
        filtered.append((chunk, paper))

    if not filtered:
        return []

    # Build embedding matrix
    embeddings = np.array([list(c.embedding) for c, _ in filtered])
    query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
    doc_norms = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)
    scores = np.dot(doc_norms, query_norm)

    top_indices = np.argsort(scores)[::-1][:top_k]
    return [_chunk_to_dict(filtered[i][0], float(scores[i])) for i in top_indices]


def _chunk_to_dict(chunk: Chunk, score: float = 0.0) -> dict:
    """Convert a Chunk ORM object to the dict shape the API expects."""
    return {
        "text": chunk.content,
        "filename": chunk.paper_filename,
        "page_num": chunk.page_num,
        "chunk_index": chunk.chunk_index,
        "section_name": chunk.section_name or "Content",
        "chemistries": [],  # populated by callers if needed
        "topics": [],
        "score": score,
    }


def hybrid_search(
    query: str,
    top_k: int = 15,
    alpha: float = 0.5,
    filter_chemistry: Optional[str] = None,
    filter_topic: Optional[str] = None,
    filter_paper_type: Optional[str] = None,
    filter_collection_filenames: Optional[set] = None,
) -> list[dict]:
    """Hybrid search: vector similarity + BM25 keyword matching.

    Same signature as rag.hybrid_search() for drop-in replacement.
    """
    from sentence_transformers import SentenceTransformer
    from rank_bm25 import BM25Okapi

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    query_embedding = model.encode([query])[0]

    # Load candidate chunks from Postgres
    with get_session() as session:
        q = (
            select(Chunk, Paper)
            .join(Paper, Paper.filename == Chunk.paper_filename)
            .where(Paper.deleted_at.is_(None))
            .where(Chunk.embedding.isnot(None))
        )
        if filter_paper_type:
            q = q.where(Paper.paper_type == filter_paper_type)
        if filter_collection_filenames:
            q = q.where(Paper.filename.in_(filter_collection_filenames))

        rows = session.execute(q).all()

    # Post-filter chemistry/topic
    candidates: list[tuple[Chunk, Paper]] = []
    for chunk, paper in rows:
        if filter_chemistry:
            chems = [c.upper() for c in _ensure_list(paper.chemistries)]
            if filter_chemistry.upper() not in chems:
                continue
        if filter_topic:
            tops = [t.lower() for t in _ensure_list(paper.topics)]
            if filter_topic.lower() not in tops:
                continue
        candidates.append((chunk, paper))

    if not candidates:
        return []

    # ── Vector scores ──
    embeddings = np.array([list(c.embedding) for c, _ in candidates])
    query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
    doc_norms = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)
    vector_scores = np.dot(doc_norms, query_norm)

    # ── BM25 scores ──
    corpus = [c.content for c, _ in candidates]
    tokenized_corpus = [doc.lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    bm25_scores = bm25.get_scores(query.lower().split())

    # ── Normalise & combine ──
    vs_min, vs_max = vector_scores.min(), vector_scores.max()
    bm_min, bm_max = bm25_scores.min(), bm25_scores.max()
    vector_norm = (vector_scores - vs_min) / (vs_max - vs_min + 1e-8)
    bm25_norm = (bm25_scores - bm_min) / (bm_max - bm_min + 1e-8)
    hybrid_scores = alpha * vector_norm + (1 - alpha) * bm25_norm

    top_indices = np.argsort(hybrid_scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        chunk, paper = candidates[idx]
        d = _chunk_to_dict(chunk)
        d["chemistries"] = _ensure_list(paper.chemistries)
        d["topics"] = _ensure_list(paper.topics)
        d["hybrid_score"] = float(hybrid_scores[idx])
        d["vector_score"] = float(vector_scores[idx])
        d["bm25_score"] = float(bm25_scores[idx])
        results.append(d)

    return results


# ═════════════════════════════════════════════════════════════════════════════
# READ STATUS  (replaces lib/read_status.py)
# ═════════════════════════════════════════════════════════════════════════════

def mark_as_read(filename: str):
    with get_session() as session:
        paper = session.get(Paper, filename)
        if paper:
            paper.is_read = True
            paper.read_marked_date = _utcnow()


def mark_as_unread(filename: str):
    with get_session() as session:
        paper = session.get(Paper, filename)
        if paper:
            paper.is_read = False
            paper.read_marked_date = None


def get_read_status(filenames: list[str]) -> dict[str, bool]:
    with get_session() as session:
        rows = session.execute(
            select(Paper.filename, Paper.is_read)
            .where(Paper.filename.in_(filenames))
        ).all()
    result = {fn: is_read for fn, is_read in rows}
    return {fn: result.get(fn, False) for fn in filenames}


def toggle_read_status(filename: str) -> bool:
    status = get_read_status([filename])
    if status.get(filename, False):
        mark_as_unread(filename)
        return False
    else:
        mark_as_read(filename)
        return True


# ═════════════════════════════════════════════════════════════════════════════
# COLLECTIONS  (replaces lib/collections.py)
# ═════════════════════════════════════════════════════════════════════════════

def create_collection(
    name: str,
    color: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    try:
        with get_session() as session:
            coll = Collection(
                name=name,
                color=color or "#6c757d",
                description=description or "",
            )
            session.add(coll)
            session.flush()
            return {"success": True, "message": f"Collection '{name}' created successfully", "id": coll.id}
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return {"success": False, "message": f"Collection '{name}' already exists"}
        return {"success": False, "message": f"Error creating collection: {e}"}


def get_all_collections() -> list[dict]:
    try:
        with get_session() as session:
            colls = session.execute(
                select(Collection).order_by(Collection.name)
            ).scalars().all()
            return [c.to_dict() for c in colls]
    except Exception as e:
        print(f"Error getting collections: {e}")
        return []


def get_collection_by_id(collection_id: int) -> Optional[dict]:
    try:
        with get_session() as session:
            coll = session.get(Collection, collection_id)
            return coll.to_dict() if coll else None
    except Exception as e:
        print(f"Error getting collection: {e}")
        return None


def add_paper_to_collection(collection_id: int, filename: str) -> dict:
    try:
        with get_session() as session:
            item = CollectionItem(
                collection_id=collection_id,
                paper_filename=filename,
            )
            session.add(item)
            session.flush()

            coll = session.get(Collection, collection_id)
            if coll:
                coll.modified_date = _utcnow()

            return {"success": True, "message": "Paper added to collection"}
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return {"success": False, "message": "Paper already in this collection"}
        return {"success": False, "message": f"Error adding paper: {e}"}


def remove_paper_from_collection(collection_id: int, filename: str) -> dict:
    try:
        with get_session() as session:
            result = session.execute(
                delete(CollectionItem).where(
                    CollectionItem.collection_id == collection_id,
                    CollectionItem.paper_filename == filename,
                )
            )
            if result.rowcount > 0:
                coll = session.get(Collection, collection_id)
                if coll:
                    coll.modified_date = _utcnow()
                return {"success": True, "message": "Paper removed from collection"}
            return {"success": False, "message": "Paper not found in collection"}
    except Exception as e:
        return {"success": False, "message": f"Error removing paper: {e}"}


def get_paper_collections(filename: str) -> list[dict]:
    try:
        with get_session() as session:
            rows = (
                session.execute(
                    select(Collection)
                    .join(CollectionItem)
                    .where(CollectionItem.paper_filename == filename)
                    .order_by(Collection.name)
                )
                .scalars()
                .all()
            )
            return [c.to_dict() for c in rows]
    except Exception as e:
        print(f"Error getting paper collections: {e}")
        return []


def get_collection_papers(collection_id: int) -> list[str]:
    try:
        with get_session() as session:
            rows = session.execute(
                select(CollectionItem.paper_filename)
                .where(CollectionItem.collection_id == collection_id)
                .order_by(CollectionItem.added_date.desc())
            ).all()
            return [r[0] for r in rows]
    except Exception as e:
        print(f"Error getting collection papers: {e}")
        return []


def delete_collection(collection_id: int) -> dict:
    try:
        with get_session() as session:
            coll = session.get(Collection, collection_id)
            if not coll:
                return {"success": False, "message": "Collection not found"}
            name = coll.name
            session.delete(coll)
            return {"success": True, "message": f"Collection '{name}' deleted"}
    except Exception as e:
        return {"success": False, "message": f"Error deleting collection: {e}"}


def rename_collection(collection_id: int, new_name: str) -> dict:
    try:
        with get_session() as session:
            coll = session.get(Collection, collection_id)
            if not coll:
                return {"success": False, "message": "Collection not found"}
            coll.name = new_name
            coll.modified_date = _utcnow()
            return {"success": True, "message": f"Collection renamed to '{new_name}'"}
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return {"success": False, "message": f"Collection '{new_name}' already exists"}
        return {"success": False, "message": f"Error renaming collection: {e}"}


def update_collection(
    collection_id: int,
    name: Optional[str] = None,
    color: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    try:
        with get_session() as session:
            coll = session.get(Collection, collection_id)
            if not coll:
                return {"success": False, "message": "Collection not found"}
            if name is not None:
                coll.name = name
            if color is not None:
                coll.color = color
            if description is not None:
                coll.description = description
            coll.modified_date = _utcnow()
            return {"success": True, "message": "Collection updated"}
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return {"success": False, "message": "Collection name already exists"}
        return {"success": False, "message": f"Error updating collection: {e}"}


def get_batch_paper_collections(filenames: list[str]) -> dict[str, list[dict]]:
    """Batch-fetch collections for multiple papers at once."""
    result: dict[str, list[dict]] = {fn: [] for fn in filenames}
    with get_session() as session:
        rows = (
            session.execute(
                select(CollectionItem.paper_filename, Collection)
                .join(Collection, Collection.id == CollectionItem.collection_id)
                .where(CollectionItem.paper_filename.in_(filenames))
                .options(selectinload(Collection.items))
            )
            .all()
        )
        for fn, coll in rows:
            result[fn].append(coll.to_dict())
    return result


# ═════════════════════════════════════════════════════════════════════════════
# QUERY HISTORY  (replaces lib/query_history.py)
# ═════════════════════════════════════════════════════════════════════════════

def save_query(
    question: str,
    answer: str,
    chunks: list[dict],
    filters: Optional[dict] = None,
) -> int:
    with get_session() as session:
        qh = QueryHistory(
            question=question,
            answer=answer,
            chunks_json=chunks,
            filters_json=filters or {},
        )
        session.add(qh)
        session.flush()
        return qh.id


def get_all_queries(limit: Optional[int] = None) -> list[dict]:
    with get_session() as session:
        q = select(QueryHistory).order_by(QueryHistory.created_at.desc())
        if limit:
            q = q.limit(limit)
        rows = session.execute(q).scalars().all()

        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                "question": r.question,
                "answer": r.answer,
                "chunks": r.chunks_json or [],
                "filters": r.filters_json or {},
                "is_starred": r.is_starred,
            }
            for r in rows
        ]


def get_query_by_id(query_id: int) -> Optional[dict]:
    with get_session() as session:
        qh = session.get(QueryHistory, query_id)
        if not qh:
            return None
        return {
            "id": qh.id,
            "timestamp": qh.timestamp.isoformat() if qh.timestamp else "",
            "question": qh.question,
            "answer": qh.answer,
            "chunks": qh.chunks_json or [],
            "filters": qh.filters_json or {},
            "is_starred": qh.is_starred,
        }


def delete_query(query_id: int) -> bool:
    with get_session() as session:
        result = session.execute(
            delete(QueryHistory).where(QueryHistory.id == query_id)
        )
        return result.rowcount > 0


def toggle_star(query_id: int) -> bool:
    with get_session() as session:
        qh = session.get(QueryHistory, query_id)
        if not qh:
            return False
        qh.is_starred = not qh.is_starred
        session.flush()
        return qh.is_starred


def get_starred_queries() -> list[dict]:
    with get_session() as session:
        rows = (
            session.execute(
                select(QueryHistory)
                .where(QueryHistory.is_starred.is_(True))
                .order_by(QueryHistory.created_at.desc())
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                "question": r.question,
                "answer": r.answer,
                "chunks": r.chunks_json or [],
                "filters": r.filters_json or {},
                "is_starred": True,
            }
            for r in rows
        ]


def clear_all_history() -> int:
    with get_session() as session:
        count = session.execute(select(func.count(QueryHistory.id))).scalar() or 0
        session.execute(delete(QueryHistory))
        return count


# ═════════════════════════════════════════════════════════════════════════════
# SETTINGS  (replaces data/settings.json)
# ═════════════════════════════════════════════════════════════════════════════

def get_setting(key: str, default=None):
    with get_session() as session:
        s = session.get(Setting, key)
        return s.value if s else default


def set_setting(key: str, value):
    with get_session() as session:
        s = session.get(Setting, key)
        if s:
            s.value = value
        else:
            session.add(Setting(key=key, value=value))


def get_all_settings() -> dict:
    with get_session() as session:
        rows = session.execute(select(Setting)).scalars().all()
        return {s.key: s.value for s in rows}


# ═════════════════════════════════════════════════════════════════════════════
# DISCOVER HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def get_library_dois_and_titles() -> Tuple[set, set]:
    """Return (set of lowercase DOIs, set of lowercase titles) for all papers."""
    with get_session() as session:
        rows = session.execute(
            select(Paper.doi, Paper.title).where(Paper.deleted_at.is_(None))
        ).all()
    dois = {r[0].lower() for r in rows if r[0]}
    titles = {r[1].lower().strip() for r in rows if r[1]}
    return dois, titles
