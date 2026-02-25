# Retrieval Quality Improvements

This document explains the three key improvements made to the RAG system's retrieval pipeline.

## Overview

The improved retrieval pipeline consists of four steps:

1. **Query Expansion** - Expand queries with related technical terms
2. **Hybrid Search** - Combine vector similarity with keyword search
3. **Reranking** - Reorder candidates by relevance
4. **Answer Generation** - Generate final answer with Claude

## 1. Query Expansion

### Problem
User queries are often brief and don't include all relevant technical terms, abbreviations, or synonyms. This causes the system to miss relevant passages.

**Example**: A user searches for "LFP degradation" but relevant papers also discuss "lithium iron phosphate", "LiFePO4", "capacity fade", "aging", etc.

### Solution
Before searching, we use Claude to expand the query with related terms:

**Original query**: "LFP degradation"

**Expanded query**: "LFP degradation lithium iron phosphate LiFePO4 capacity fade aging calendar life cycle life capacity loss performance degradation mechanisms"

### Implementation
```python
def expand_query(query: str, api_key: str) -> str:
    """Expand query with related technical terms using Claude."""
    # Uses Claude to generate related terms, synonyms, abbreviations
    # Falls back to original query if expansion fails
```

### Benefits
- Finds more relevant passages
- Handles abbreviations and synonyms automatically
- Improves recall (finds more relevant documents)

## 2. Hybrid Search (Vector + BM25)

### Problem
Pure vector search is great for semantic similarity but can miss exact keyword matches. For technical papers, exact terms matter:
- Cell model numbers (e.g., "18650", "NCM811")
- Author names
- Specific chemical formulas
- Standard abbreviations

### Solution
Combine two complementary search methods:

1. **Vector Search (Semantic)**
   - Uses sentence embeddings
   - Understands meaning and context
   - Good for: Related concepts, paraphrases, semantic similarity

2. **BM25 Search (Keyword)**
   - Classic information retrieval algorithm
   - Matches exact keywords with TF-IDF-like scoring
   - Good for: Exact terms, rare keywords, proper nouns

### How It Works
```python
# 1. Compute vector similarity scores (0-1)
vector_scores = cosine_similarity(query_embedding, doc_embeddings)

# 2. Compute BM25 keyword scores
bm25_scores = bm25.get_scores(tokenized_query)

# 3. Normalize both to [0, 1]
vector_scores_norm = normalize(vector_scores)
bm25_scores_norm = normalize(bm25_scores)

# 4. Combine with configurable weight (default: alpha=0.5)
hybrid_scores = alpha * vector_scores_norm + (1 - alpha) * bm25_scores_norm

# 5. Return top-k by hybrid score
```

### Configuration
The `alpha` parameter controls the balance:
- `alpha=1.0`: Pure vector search (semantic only)
- `alpha=0.5`: Equal weight (default, balanced)
- `alpha=0.0`: Pure BM25 (keyword only)

Default is 0.5 (50/50 split) which provides the best balance for technical papers.

### Benefits
- Combines strengths of both approaches
- Better handles technical terminology
- More robust to query variations

## 3. Reranking

### Problem
Initial retrieval (even hybrid) is fast but may not perfectly order results by relevance. The top 5 chunks might not be the actual top 5.

### Solution
Two-stage retrieval:

**Stage 1 - Fast Retrieval**: Get 15 candidates using hybrid search

**Stage 2 - Precise Reranking**: Use Claude to score each candidate's relevance to the original question, return top 5

### How It Works
```python
# 1. Hybrid search retrieves 15 candidates
candidates = hybrid_search(expanded_query, top_k=15)

# 2. Send candidates to Claude for ranking
# Claude receives: original query + preview of each chunk
# Claude returns: ranked list of indices [3, 0, 7, 1, 5, ...]

# 3. Reorder candidates and take top 5
final_chunks = reorder_by_ranking(candidates)[:5]
```

### Why This Works
- Claude understands nuanced relevance better than pure similarity scores
- Can distinguish between "mentions the topic" vs "directly answers the question"
- Considers context that embedding models might miss

### Benefits
- Higher precision (top 5 are truly the most relevant)
- Better quality answers
- Fewer irrelevant sources in final answer

## Performance Considerations

### API Costs
The improved pipeline uses Claude API for two steps:
1. Query expansion: ~100 tokens in, ~50 tokens out
2. Reranking: ~1500 tokens in (15 chunks × 100 token preview), ~50 tokens out

Total: ~1700 tokens per query (minimal cost with Claude Sonnet 4.5)

### Latency
- Query expansion: ~1 second
- Hybrid search: ~2-3 seconds (depends on corpus size)
- Reranking: ~2 seconds
- Answer generation: ~5-10 seconds

Total: ~10-15 seconds per query (acceptable for research use)

### Optimization Options

**Disable query expansion**:
```python
chunks = retrieve_with_hybrid_and_reranking(
    question=question,
    api_key=api_key,
    enable_query_expansion=False  # Skip expansion
)
```

**Disable reranking**:
```python
chunks = retrieve_with_hybrid_and_reranking(
    question=question,
    api_key=api_key,
    enable_reranking=False  # Skip reranking
)
```

**Adjust hybrid search weight**:
```python
chunks = retrieve_with_hybrid_and_reranking(
    question=question,
    api_key=api_key,
    alpha=0.7  # 70% vector, 30% BM25
)
```

**Retrieve fewer candidates**:
```python
chunks = retrieve_with_hybrid_and_reranking(
    question=question,
    api_key=api_key,
    n_candidates=10  # Only 10 candidates (faster reranking)
)
```

## Comparison: Old vs New

### Old Pipeline
1. Embed query
2. Vector search → top 5 chunks
3. Send to Claude for answer

**Limitations**:
- Misses exact keyword matches
- No query understanding or expansion
- Top 5 might not be best 5

### New Pipeline
1. Expand query with Claude
2. Hybrid search → top 15 candidates
3. Rerank with Claude → top 5
4. Send to Claude for answer

**Improvements**:
- Finds more relevant passages (expansion + hybrid)
- Better ranking quality (reranking)
- More robust to query variations

## Example Queries Where This Helps

### Example 1: Abbreviations
**Query**: "LFP cycle life"

**Old**: Might miss passages that use "lithium iron phosphate" instead of "LFP"

**New**: Query expansion adds "lithium iron phosphate LiFePO4" → finds all relevant passages

### Example 2: Exact Terms
**Query**: "NCM811 degradation"

**Old**: Pure vector search might return general degradation passages

**New**: BM25 component ensures "NCM811" is matched exactly → finds specific passages about NCM811

### Example 3: Ranking Quality
**Query**: "How does temperature affect cycle life?"

**Old**: Top 5 might include passages that only mention temperature or cycle life separately

**New**: Reranking identifies passages that actually discuss the relationship between temperature and cycle life

## Testing

Run the test suite to verify the implementation:

```bash
python test_retrieval.py
```

This checks:
- All imports work correctly
- New functions exist and are callable
- Database connection works

## References

- **BM25**: Robertson, S., & Zaragoza, H. (2009). "The Probabilistic Relevance Framework: BM25 and Beyond"
- **Hybrid Search**: Combines dense (neural) and sparse (lexical) retrieval methods
- **Reranking**: Two-stage retrieval is standard in modern search systems

## Future Improvements

Possible enhancements:
1. **Cross-encoder reranking**: Use a dedicated reranking model (faster than LLM)
2. **Query understanding**: Classify query intent (definition, comparison, how-to, etc.)
3. **Chunk fusion**: Combine overlapping chunks intelligently
4. **Metadata filtering**: Use paper metadata (chemistry, topic) in scoring
5. **Caching**: Cache expanded queries and BM25 index for faster retrieval
