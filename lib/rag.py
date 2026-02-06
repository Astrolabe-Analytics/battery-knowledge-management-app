"""
RAG Backend Module
Handles all business logic for the battery papers RAG system:
- Database operations (ChromaDB)
- Model loading (sentence transformers)
- Search and retrieval
- LLM interactions (Claude API)
"""

import os
import json
from pathlib import Path
from typing import Optional, List, Tuple
import chromadb
from sentence_transformers import SentenceTransformer
from anthropic import Anthropic
from rank_bm25 import BM25Okapi
import numpy as np

# Import retry utilities
from .retry import anthropic_api_call_with_retry


# Configuration
DB_DIR = Path(__file__).parent.parent / "data" / "chroma_db"
PAPERS_DIR = Path(__file__).parent.parent / "papers"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "battery_papers"
TOP_K = 5
CLAUDE_MODEL = "claude-opus-4-5-20251101"  # Using Opus 4.5 for highest quality answers


class EmbeddingModelLoader:
    """Singleton for loading and caching the embedding model."""
    _instance = None
    _model = None

    @classmethod
    def get_model(cls):
        """Load and cache the embedding model."""
        if cls._model is None:
            cls._model = SentenceTransformer(EMBEDDING_MODEL)
        return cls._model


class DatabaseClient:
    """Handles ChromaDB operations."""
    _client = None
    _collection = None

    @classmethod
    def get_collection(cls):
        """Load and cache the ChromaDB collection."""
        if cls._collection is None:
            if not DB_DIR.exists():
                raise FileNotFoundError(
                    f"Database not found at {DB_DIR}. "
                    "Please run 'python scripts/ingest.py' first."
                )

            try:
                cls._client = chromadb.PersistentClient(path=str(DB_DIR))
                cls._collection = cls._client.get_collection(name=COLLECTION_NAME)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to load collection: {e}. "
                    "Please run 'python scripts/ingest.py' first."
                )

        return cls._collection

    @classmethod
    def clear_cache(cls):
        """Clear the cached collection to force reload."""
        cls._collection = None
        cls._client = None


def get_api_key_from_env() -> Optional[str]:
    """Get Anthropic API key from environment variable."""
    return os.environ.get("ANTHROPIC_API_KEY")


def get_paper_library() -> list[dict]:
    """
    Get all unique papers with their aggregated metadata.

    Returns:
        List of dicts with paper info: filename, title, authors, year, journal,
        doi, author_keywords, chemistries, topics, application, paper_type, num_pages
    """
    collection = DatabaseClient.get_collection()
    all_results = collection.get(include=["metadatas"])

    papers = {}
    for metadata in all_results['metadatas']:
        filename = metadata['filename']
        if filename not in papers:
            papers[filename] = {
                'filename': filename,
                'title': metadata.get('title', filename.replace('.pdf', '')),
                'authors': metadata.get('authors', ''),
                'year': metadata.get('year', ''),
                'journal': metadata.get('journal', ''),
                'doi': metadata.get('doi', ''),
                'author_keywords': set(),
                'chemistries': set(),
                'topics': set(),
                'application': metadata.get('application', 'general'),
                'paper_type': metadata.get('paper_type', 'experimental'),
                'pages': set()
            }

        # Aggregate metadata
        if metadata.get('author_keywords'):
            papers[filename]['author_keywords'].update(metadata['author_keywords'].split(';'))
        if metadata.get('chemistries'):
            papers[filename]['chemistries'].update(metadata['chemistries'].split(','))
        if metadata.get('topics'):
            papers[filename]['topics'].update(metadata['topics'].split(','))
        papers[filename]['pages'].add(metadata['page_num'])

    # Convert sets to sorted lists/counts
    for paper in papers.values():
        paper['author_keywords'] = sorted([k for k in paper['author_keywords'] if k])
        paper['chemistries'] = sorted([c for c in paper['chemistries'] if c])
        paper['topics'] = sorted([t for t in paper['topics'] if t])
        paper['num_pages'] = len(paper['pages'])
        del paper['pages']

    # Load additional data from metadata.json, including metadata-only papers
    metadata_file = Path("data/metadata.json")
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            full_metadata = json.load(f)

            # Update existing papers with date_added
            for paper in papers.values():
                filename = paper['filename']
                if filename in full_metadata:
                    paper['date_added'] = full_metadata[filename].get('date_added', '')
                else:
                    paper['date_added'] = ''

            # Add metadata-only papers (not in ChromaDB yet)
            for filename, meta in full_metadata.items():
                if filename not in papers:
                    # This is a metadata-only paper
                    papers[filename] = {
                        'filename': filename,
                        'title': meta.get('title', filename.replace('.pdf', '')),
                        'authors': '; '.join(meta.get('authors', [])) if isinstance(meta.get('authors'), list) else meta.get('authors', ''),
                        'year': meta.get('year', ''),
                        'journal': meta.get('journal', ''),
                        'doi': meta.get('doi', ''),
                        'author_keywords': meta.get('author_keywords', []),
                        'chemistries': meta.get('chemistries', []),
                        'topics': meta.get('topics', []),
                        'application': meta.get('application', 'general'),
                        'paper_type': meta.get('paper_type', 'reference'),
                        'num_pages': 0,  # No PDF yet
                        'date_added': meta.get('date_added', '')
                    }

            # Filter out deleted papers (papers with deleted_at field)
            papers = {k: v for k, v in papers.items() if not full_metadata.get(k, {}).get('deleted_at')}

    return list(papers.values())


def get_filter_options() -> dict:
    """
    Extract unique values for filters.

    Returns:
        Dict with keys: chemistries, topics, paper_types
    """
    collection = DatabaseClient.get_collection()
    all_results = collection.get(include=["metadatas"])

    chemistries = set()
    topics = set()
    paper_types = set()

    for metadata in all_results['metadatas']:
        if metadata.get('chemistries'):
            chemistries.update(metadata['chemistries'].split(','))
        if metadata.get('topics'):
            topics.update(metadata['topics'].split(','))
        if metadata.get('paper_type'):
            paper_types.add(metadata['paper_type'])

    return {
        'chemistries': sorted([c for c in chemistries if c]),
        'topics': sorted([t for t in topics if t]),
        'paper_types': sorted(paper_types)
    }


def get_paper_details(filename: str) -> Optional[dict]:
    """
    Get detailed information for a specific paper.

    Args:
        filename: The PDF filename

    Returns:
        Dict with paper details including preview chunks, or None if not found
    """
    collection = DatabaseClient.get_collection()

    results = collection.get(
        where={"filename": filename},
        include=["documents", "metadatas"]
    )

    # Check if paper exists in ChromaDB
    if results['documents']:
        # Paper has chunks in ChromaDB - get preview chunks
        first_chunks = []
        for i, (doc, meta) in enumerate(zip(results['documents'][:3], results['metadatas'][:3])):
            first_chunks.append({
                'page': meta['page_num'],
                'text': doc
            })

        details = {
            'filename': filename,
            'title': results['metadatas'][0].get('title', filename),
            'authors': results['metadatas'][0].get('authors', '').split(';'),
            'year': results['metadatas'][0].get('year', ''),
            'journal': results['metadatas'][0].get('journal', ''),
            'doi': results['metadatas'][0].get('doi', ''),
            'author_keywords': results['metadatas'][0].get('author_keywords', '').split(';') if results['metadatas'][0].get('author_keywords') else [],
            'chemistries': results['metadatas'][0].get('chemistries', '').split(','),
            'topics': results['metadatas'][0].get('topics', '').split(','),
            'application': results['metadatas'][0].get('application', 'general'),
            'paper_type': results['metadatas'][0].get('paper_type', 'experimental'),
            'preview_chunks': first_chunks
        }
    else:
        # Paper not in ChromaDB - might be metadata-only
        # Try loading from metadata.json
        metadata_file = Path("data/metadata.json")
        if not metadata_file.exists():
            return None

        with open(metadata_file, 'r', encoding='utf-8') as f:
            full_metadata = json.load(f)
            if filename not in full_metadata:
                return None

            paper_meta = full_metadata[filename]

            # Build details from metadata.json
            details = {
                'filename': filename,
                'title': paper_meta.get('title', filename.replace('.pdf', '')),
                'authors': paper_meta.get('authors', []) if isinstance(paper_meta.get('authors'), list) else [paper_meta.get('authors', '')],
                'year': paper_meta.get('year', ''),
                'journal': paper_meta.get('journal', ''),
                'doi': paper_meta.get('doi', ''),
                'author_keywords': paper_meta.get('author_keywords', []),
                'chemistries': paper_meta.get('chemistries', []),
                'topics': paper_meta.get('topics', []),
                'application': paper_meta.get('application', 'general'),
                'paper_type': paper_meta.get('paper_type', 'reference'),
                'preview_chunks': [],  # No chunks for metadata-only papers
                'references': paper_meta.get('references', []),
                'date_added': paper_meta.get('date_added', ''),
                'abstract': paper_meta.get('abstract', ''),
                'volume': paper_meta.get('volume', ''),
                'issue': paper_meta.get('issue', ''),
                'pages': paper_meta.get('pages', '')
            }
            return details

    # Load additional fields from metadata.json for papers with chunks
    metadata_file = Path("data/metadata.json")
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            full_metadata = json.load(f)
            if filename in full_metadata:
                paper_meta = full_metadata[filename]
                details['references'] = paper_meta.get('references', [])
                details['date_added'] = paper_meta.get('date_added', '')
                details['abstract'] = paper_meta.get('abstract', '')
                details['volume'] = paper_meta.get('volume', '')
                details['issue'] = paper_meta.get('issue', '')
                details['pages'] = paper_meta.get('pages', '')

    return details


def retrieve_relevant_chunks(
    question: str,
    top_k: int = TOP_K,
    filter_chemistry: Optional[str] = None,
    filter_topic: Optional[str] = None,
    filter_paper_type: Optional[str] = None
) -> list[dict]:
    """
    Retrieve top-K relevant chunks for the question using semantic search.

    Args:
        question: User's question
        top_k: Number of chunks to retrieve
        filter_chemistry: Optional chemistry filter (e.g., "NMC", "LFP")
        filter_topic: Optional topic filter (e.g., "degradation", "SOH")
        filter_paper_type: Optional paper type filter (e.g., "experimental")

    Returns:
        List of chunk dicts with text, metadata, and section info
    """
    model = EmbeddingModelLoader.get_model()
    collection = DatabaseClient.get_collection()

    # Generate query embedding
    question_embedding = model.encode([question])[0].tolist()

    # Query ChromaDB - get more results for post-filtering if filters are active
    # ChromaDB doesn't support substring matching, so we filter in Python
    n_results = top_k * 10 if (filter_chemistry or filter_topic) else top_k

    # Build where clause for paper_type (exact match supported)
    where_clause = {}
    if filter_paper_type:
        where_clause = {"paper_type": filter_paper_type}

    try:
        query_params = {
            "query_embeddings": [question_embedding],
            "n_results": n_results
        }
        if where_clause:
            query_params["where"] = where_clause

        results = collection.query(**query_params)
    except Exception as e:
        raise RuntimeError(f"Failed to query database: {e}")

    # Format and filter results
    chunks = []
    if results['documents'] and results['documents'][0]:
        for i in range(len(results['documents'][0])):
            metadata = results['metadatas'][0][i]

            # Extract metadata
            chemistries_str = metadata.get('chemistries', '')
            topics_str = metadata.get('topics', '')
            chemistries = [c.strip() for c in chemistries_str.split(',') if c.strip()]
            topics = [t.strip() for t in topics_str.split(',') if t.strip()]

            # Apply filters (post-filtering)
            if filter_chemistry and filter_chemistry.upper() not in chemistries:
                continue
            if filter_topic and filter_topic.lower() not in topics:
                continue

            chunk = {
                'text': results['documents'][0][i],
                'filename': metadata['filename'],
                'page_num': metadata['page_num'],
                'chunk_index': metadata['chunk_index'],
                'section_name': metadata.get('section_name', 'Content'),
                'chemistries': chemistries,
                'topics': topics
            }
            chunks.append(chunk)

            # Stop once we have enough
            if len(chunks) >= top_k:
                break

    return chunks[:top_k]


def retrieve_with_hybrid_and_reranking(
    question: str,
    api_key: str,
    top_k: int = 5,
    n_candidates: int = 15,
    alpha: float = 0.5,
    filter_chemistry: Optional[str] = None,
    filter_topic: Optional[str] = None,
    filter_paper_type: Optional[str] = None,
    filter_collection_filenames: Optional[set] = None,
    enable_query_expansion: bool = True,
    enable_reranking: bool = True
) -> list[dict]:
    """
    Improved retrieval pipeline combining query expansion, hybrid search, and reranking.

    Pipeline:
    1. Query expansion: Use Claude to expand query with related technical terms
    2. Hybrid search: Retrieve n_candidates chunks using vector + BM25
    3. Reranking: Use Claude to reorder by relevance, return top_k

    Args:
        question: User's question
        api_key: Anthropic API key (required for expansion and reranking)
        top_k: Final number of chunks to return after reranking
        n_candidates: Number of chunks to retrieve before reranking
        alpha: Weight for vector search in hybrid (0.5 = equal vector/BM25)
        filter_chemistry: Optional chemistry filter
        filter_topic: Optional topic filter
        filter_paper_type: Optional paper type filter
        filter_collection_filenames: Optional set of filenames to limit search to a collection
        enable_query_expansion: Whether to expand query (default: True)
        enable_reranking: Whether to rerank results (default: True)

    Returns:
        List of top_k most relevant chunks after reranking
    """
    # Step 1: Query expansion (if enabled and API key available)
    search_query = question
    if enable_query_expansion and api_key:
        try:
            search_query = expand_query(question, api_key)
            # Use expanded query for search, but keep original for reranking/display
        except Exception:
            # Fall back to original query if expansion fails
            search_query = question

    # Step 2: Hybrid search - retrieve more candidates
    candidates = hybrid_search(
        query=search_query,
        top_k=n_candidates,
        alpha=alpha,
        filter_chemistry=filter_chemistry,
        filter_topic=filter_topic,
        filter_paper_type=filter_paper_type,
        filter_collection_filenames=filter_collection_filenames
    )

    if not candidates:
        return []

    # Step 3: Reranking (if enabled and API key available)
    if enable_reranking and api_key and len(candidates) > top_k:
        final_chunks = rerank_chunks(
            query=question,  # Use original question for reranking
            chunks=candidates,
            api_key=api_key,
            top_k=top_k
        )
    else:
        # No reranking needed if we have fewer candidates than top_k
        final_chunks = candidates[:top_k]

    return final_chunks


@anthropic_api_call_with_retry
def _call_claude_api(prompt: str, api_key: str, model: str, max_tokens: int) -> str:
    """Internal function to call Claude API with retry logic."""
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def query_claude(question: str, chunks: list[dict], api_key: str) -> str:
    """
    Send question + context to Claude and get answer.

    Args:
        question: User's question
        chunks: List of relevant chunks from retrieve_relevant_chunks()
        api_key: Anthropic API key

    Returns:
        Claude's answer as a string

    Raises:
        RuntimeError: If API call fails after retries
    """
    # Build context from chunks
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        section_info = f", section: {chunk['section_name']}" if chunk.get('section_name') else ""
        context_parts.append(
            f"[Document {i}: {chunk['filename']}, page {chunk['page_num']}{section_info}]\n{chunk['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    # Build prompt
    prompt = f"""You are a helpful AI assistant specializing in battery research.
Answer the following question based on the provided research paper excerpts.

Important instructions:
- Cite your sources by referring to the document number and page (e.g., "According to Document 1, page 5...")
- If the information isn't in the provided excerpts, say so clearly
- Be specific and technical when appropriate
- If multiple papers discuss the same topic, mention all relevant sources

Context from research papers:

{context}

---

Question: {question}

Please provide a detailed answer with citations:"""

    try:
        return _call_claude_api(prompt, api_key, CLAUDE_MODEL, 2000)
    except Exception as e:
        raise RuntimeError(f"Failed to query Claude API after retries: {e}")


def get_collection_count() -> int:
    """Get total number of chunks in the collection."""
    collection = DatabaseClient.get_collection()
    return collection.count()


def check_pdf_exists(filename: str) -> bool:
    """Check if a PDF file exists in the papers directory."""
    pdf_path = PAPERS_DIR / filename
    return pdf_path.exists()


def get_pdf_path(filename: str) -> Path:
    """Get the full path to a PDF file."""
    return PAPERS_DIR / filename


@anthropic_api_call_with_retry
def _call_claude_for_query_expansion(query: str, api_key: str) -> str:
    """Internal function to call Claude for query expansion."""
    prompt = f"""You are a battery research expert. Expand this search query with related technical terms, synonyms, abbreviations, and related concepts.

Original query: {query}

Provide an expanded query that includes:
- Synonyms and related terms
- Standard abbreviations (e.g., LFP = lithium iron phosphate = LiFePO4)
- Related concepts and phenomena
- Alternative phrasings

Return ONLY the expanded query as a single line of keywords and phrases, no explanation.

Example:
Input: "LFP degradation"
Output: LFP degradation lithium iron phosphate LiFePO4 capacity fade aging calendar life cycle life capacity loss performance degradation mechanisms

Expanded query:"""

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=200,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def expand_query(query: str, api_key: str) -> str:
    """
    Expand query with related technical terms using Claude.

    Args:
        query: Original user query
        api_key: Anthropic API key

    Returns:
        Expanded query string with additional terms
    """
    try:
        expanded = _call_claude_for_query_expansion(query, api_key)
        return expanded if expanded else query
    except Exception as e:
        # If expansion fails, fall back to original query
        return query


@anthropic_api_call_with_retry
def _call_claude_for_reranking(query: str, chunks: List[dict], api_key: str) -> List[int]:
    """Internal function to call Claude for reranking chunks."""
    # Build prompt with chunks
    chunks_text = []
    for i, chunk in enumerate(chunks):
        chunks_text.append(
            f"[{i}] {chunk['filename']}, page {chunk['page_num']}\n"
            f"{chunk['text'][:300]}..."
        )

    prompt = f"""You are a relevance scoring expert for battery research papers.

Question: {query}

Rank these passages by relevance to the question. Return ONLY a comma-separated list of indices in order from most to least relevant (e.g., "3,0,7,1,5").

Passages:
{chr(10).join(chunks_text)}

Ranking (most relevant first):"""

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=100,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    # Parse the response to get indices
    result = response.content[0].text.strip()
    try:
        indices = [int(x.strip()) for x in result.split(',')]
        return indices
    except:
        # If parsing fails, return original order
        return list(range(len(chunks)))


def rerank_chunks(query: str, chunks: List[dict], api_key: str, top_k: int = 5) -> List[dict]:
    """
    Rerank chunks using Claude-based relevance scoring.

    Args:
        query: User's question
        chunks: List of candidate chunks
        api_key: Anthropic API key
        top_k: Number of top chunks to return after reranking

    Returns:
        Reranked list of top_k chunks
    """
    if len(chunks) <= top_k:
        return chunks

    try:
        # Get reranked indices from Claude
        ranked_indices = _call_claude_for_reranking(query, chunks, api_key)

        # Reorder chunks according to ranking
        reranked = []
        for idx in ranked_indices[:top_k]:
            if 0 <= idx < len(chunks):
                reranked.append(chunks[idx])

        # If we don't have enough, fill with remaining chunks
        if len(reranked) < top_k:
            remaining = [c for i, c in enumerate(chunks) if i not in ranked_indices[:top_k]]
            reranked.extend(remaining[:top_k - len(reranked)])

        return reranked[:top_k]

    except Exception as e:
        # If reranking fails, return top_k chunks as-is
        return chunks[:top_k]


def hybrid_search(
    query: str,
    top_k: int = 15,
    alpha: float = 0.5,
    filter_chemistry: Optional[str] = None,
    filter_topic: Optional[str] = None,
    filter_paper_type: Optional[str] = None,
    filter_collection_filenames: Optional[set] = None
) -> List[dict]:
    """
    Hybrid search combining vector similarity (semantic) with BM25 (keyword).

    Args:
        query: Search query
        top_k: Number of results to retrieve before reranking
        alpha: Weight for vector search (1-alpha for BM25). 0.5 = equal weight
        filter_chemistry: Optional chemistry filter
        filter_topic: Optional topic filter
        filter_paper_type: Optional paper type filter
        filter_collection_filenames: Optional set of filenames to limit search to a collection

    Returns:
        List of chunks ranked by hybrid score
    """
    model = EmbeddingModelLoader.get_model()
    collection = DatabaseClient.get_collection()

    # Get all documents for BM25 (need corpus for keyword search)
    # Note: For large collections, this should be optimized with caching
    all_results = collection.get(include=["documents", "metadatas"])
    corpus = all_results['documents']
    metadatas = all_results['metadatas']

    # Apply filters to build candidate set
    filtered_indices = []
    for i, metadata in enumerate(metadatas):
        # Extract metadata
        chemistries_str = metadata.get('chemistries', '')
        topics_str = metadata.get('topics', '')
        chemistries = [c.strip() for c in chemistries_str.split(',') if c.strip()]
        topics = [t.strip() for t in topics_str.split(',') if t.strip()]
        paper_type = metadata.get('paper_type', '')
        filename = metadata.get('filename', '')

        # Apply filters
        if filter_chemistry and filter_chemistry.upper() not in chemistries:
            continue
        if filter_topic and filter_topic.lower() not in topics:
            continue
        if filter_paper_type and paper_type != filter_paper_type:
            continue
        if filter_collection_filenames and filename not in filter_collection_filenames:
            continue

        filtered_indices.append(i)

    # If no candidates after filtering, return empty
    if not filtered_indices:
        return []

    # Build filtered corpus for BM25
    filtered_corpus = [corpus[i] for i in filtered_indices]
    filtered_metadatas = [metadatas[i] for i in filtered_indices]

    # 1. Vector search (semantic similarity)
    query_embedding = model.encode([query])[0].tolist()

    # Get vector scores for filtered documents
    # For simplicity, we'll compute dot product similarity
    # (ChromaDB uses cosine similarity internally)
    doc_embeddings = model.encode(filtered_corpus, show_progress_bar=False)
    query_emb = np.array(query_embedding)
    doc_embs = np.array(doc_embeddings)

    # Normalize for cosine similarity
    query_norm = query_emb / (np.linalg.norm(query_emb) + 1e-8)
    doc_norms = doc_embs / (np.linalg.norm(doc_embs, axis=1, keepdims=True) + 1e-8)

    vector_scores = np.dot(doc_norms, query_norm)

    # 2. BM25 search (keyword matching)
    tokenized_corpus = [doc.lower().split() for doc in filtered_corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    tokenized_query = query.lower().split()
    bm25_scores = bm25.get_scores(tokenized_query)

    # Normalize scores to [0, 1]
    vector_scores_norm = (vector_scores - vector_scores.min()) / (vector_scores.max() - vector_scores.min() + 1e-8)
    bm25_scores_norm = (bm25_scores - bm25_scores.min()) / (bm25_scores.max() - bm25_scores.min() + 1e-8)

    # 3. Combine scores
    hybrid_scores = alpha * vector_scores_norm + (1 - alpha) * bm25_scores_norm

    # 4. Get top-k results
    top_indices = np.argsort(hybrid_scores)[::-1][:top_k]

    # 5. Format results
    chunks = []
    for idx in top_indices:
        metadata = filtered_metadatas[idx]

        chemistries_str = metadata.get('chemistries', '')
        topics_str = metadata.get('topics', '')
        chemistries = [c.strip() for c in chemistries_str.split(',') if c.strip()]
        topics = [t.strip() for t in topics_str.split(',') if t.strip()]

        chunk = {
            'text': filtered_corpus[idx],
            'filename': metadata['filename'],
            'page_num': metadata['page_num'],
            'chunk_index': metadata['chunk_index'],
            'section_name': metadata.get('section_name', 'Content'),
            'chemistries': chemistries,
            'topics': topics,
            'hybrid_score': float(hybrid_scores[idx]),
            'vector_score': float(vector_scores[idx]),
            'bm25_score': float(bm25_scores[idx])
        }
        chunks.append(chunk)

    return chunks
