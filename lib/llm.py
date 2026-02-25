"""
LLM helpers — Claude API interactions for RAG.

Extracted from rag.py during Postgres migration.  Contains only the
pure LLM functions with zero database dependencies.
"""

import os
from typing import Optional, List

from anthropic import Anthropic
from .retry import anthropic_api_call_with_retry

# Model for interactive RAG queries (expansion, reranking, answering)
CLAUDE_MODEL = "claude-opus-4-6"


# ── API key ──────────────────────────────────────────────────────────────────

def get_api_key_from_env() -> Optional[str]:
    """Get Anthropic API key from environment variable."""
    return os.environ.get("ANTHROPIC_API_KEY")


# ── Core Claude call ─────────────────────────────────────────────────────────

@anthropic_api_call_with_retry
def _call_claude_api(prompt: str, api_key: str, model: str, max_tokens: int) -> str:
    """Internal function to call Claude API with retry logic."""
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ── RAG answer generation ────────────────────────────────────────────────────

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
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        section_info = f", section: {chunk['section_name']}" if chunk.get('section_name') else ""
        context_parts.append(
            f"[Document {i}: {chunk['filename']}, page {chunk['page_num']}{section_info}]\n{chunk['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

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


# ── Query expansion ──────────────────────────────────────────────────────────

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
        messages=[{"role": "user", "content": prompt}],
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
    except Exception:
        return query


# ── Chunk reranking ──────────────────────────────────────────────────────────

@anthropic_api_call_with_retry
def _call_claude_for_reranking(query: str, chunks: List[dict], api_key: str) -> List[int]:
    """Internal function to call Claude for reranking chunks."""
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
        messages=[{"role": "user", "content": prompt}],
    )

    result = response.content[0].text.strip()
    try:
        indices = [int(x.strip()) for x in result.split(',')]
        return indices
    except Exception:
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
        ranked_indices = _call_claude_for_reranking(query, chunks, api_key)
        reranked = []
        for idx in ranked_indices[:top_k]:
            if 0 <= idx < len(chunks):
                reranked.append(chunks[idx])
        if len(reranked) < top_k:
            remaining = [c for i, c in enumerate(chunks) if i not in ranked_indices[:top_k]]
            reranked.extend(remaining[:top_k - len(reranked)])
        return reranked[:top_k]
    except Exception:
        return chunks[:top_k]
