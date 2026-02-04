"""
RAG Backend Module
Handles all business logic for the battery papers RAG system:
- Database operations (ChromaDB)
- Model loading (sentence transformers)
- Search and retrieval
- LLM interactions (Claude API)
"""

import os
from pathlib import Path
from typing import Optional
import chromadb
from sentence_transformers import SentenceTransformer
from anthropic import Anthropic

# Import retry utilities
from .retry import anthropic_api_call_with_retry


# Configuration
DB_DIR = Path(__file__).parent.parent / "data" / "chroma_db"
PAPERS_DIR = Path(__file__).parent.parent / "papers"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "battery_papers"
TOP_K = 5
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"


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


def get_api_key_from_env() -> Optional[str]:
    """Get Anthropic API key from environment variable."""
    return os.environ.get("ANTHROPIC_API_KEY")


def get_paper_library() -> list[dict]:
    """
    Get all unique papers with their aggregated metadata.

    Returns:
        List of dicts with paper info: filename, chemistries, topics,
        application, paper_type, num_pages
    """
    collection = DatabaseClient.get_collection()
    all_results = collection.get(include=["metadatas"])

    papers = {}
    for metadata in all_results['metadatas']:
        filename = metadata['filename']
        if filename not in papers:
            papers[filename] = {
                'filename': filename,
                'chemistries': set(),
                'topics': set(),
                'application': metadata.get('application', 'general'),
                'paper_type': metadata.get('paper_type', 'experimental'),
                'pages': set()
            }

        # Aggregate metadata
        if metadata.get('chemistries'):
            papers[filename]['chemistries'].update(metadata['chemistries'].split(','))
        if metadata.get('topics'):
            papers[filename]['topics'].update(metadata['topics'].split(','))
        papers[filename]['pages'].add(metadata['page_num'])

    # Convert sets to sorted lists/counts
    for paper in papers.values():
        paper['chemistries'] = sorted([c for c in paper['chemistries'] if c])
        paper['topics'] = sorted([t for t in paper['topics'] if t])
        paper['num_pages'] = len(paper['pages'])
        del paper['pages']

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

    if not results['documents']:
        return None

    # Get first page or first few chunks
    first_chunks = []
    for i, (doc, meta) in enumerate(zip(results['documents'][:3], results['metadatas'][:3])):
        first_chunks.append({
            'page': meta['page_num'],
            'text': doc
        })

    return {
        'filename': filename,
        'chemistries': results['metadatas'][0].get('chemistries', '').split(','),
        'topics': results['metadatas'][0].get('topics', '').split(','),
        'application': results['metadatas'][0].get('application', 'general'),
        'paper_type': results['metadatas'][0].get('paper_type', 'experimental'),
        'preview_chunks': first_chunks
    }


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
