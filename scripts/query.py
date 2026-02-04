#!/usr/bin/env python3
"""
Query script for battery research papers RAG system.
Accepts questions and returns answers with citations from the papers.

Now uses improved retrieval pipeline with:
- Query expansion (Claude expands queries with related terms)
- Hybrid search (combines vector similarity + BM25 keyword search)
- Reranking (retrieves 15 candidates, reorders by relevance, returns top 5)
"""

import os
import sys
import argparse

# Add parent directory to path to import lib module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib import rag

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


# Configuration
TOP_K = 5  # Final number of chunks after reranking
N_CANDIDATES = 15  # Number of candidates to retrieve before reranking
ALPHA = 0.5  # Balance between vector (0.5) and BM25 (0.5) search


def get_api_key() -> str:
    """Get Anthropic API key from environment."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\nERROR: ANTHROPIC_API_KEY environment variable not set")
        print("Please set it with: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)
    return api_key


def format_citations(chunks: list[dict]) -> str:
    """Format citations for display."""
    citations = []
    seen = set()

    for i, chunk in enumerate(chunks, 1):
        key = (chunk['filename'], chunk['page_num'], chunk.get('section_name', ''))
        if key not in seen:
            section_info = f" ({chunk['section_name']})" if chunk.get('section_name') and chunk['section_name'] != 'Content' else ""
            citations.append(f"  [{i}] {chunk['filename']}, page {chunk['page_num']}{section_info}")
            seen.add(key)

    return "\n".join(citations)


def interactive_mode(api_key: str):
    """Run in interactive mode, accepting multiple questions."""
    print("\n" + "="*60)
    print("Interactive Query Mode")
    print("="*60)
    print("Enter your questions (or 'quit' to exit)\n")

    while True:
        try:
            question = input("\nQuestion: ").strip()

            if question.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye!")
                break

            if not question:
                continue

            print()
            process_question(question, api_key)

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except EOFError:
            print("\n\nGoodbye!")
            break


def process_question(question: str, api_key: str,
                    filter_chemistry: str = None, filter_topic: str = None,
                    filter_paper_type: str = None):
    """Process a single question using the improved retrieval pipeline."""
    # Build filter message
    filter_msg = []
    if filter_chemistry:
        filter_msg.append(f"chemistry={filter_chemistry}")
    if filter_topic:
        filter_msg.append(f"topic={filter_topic}")
    if filter_paper_type:
        filter_msg.append(f"type={filter_paper_type}")

    filter_str = f" ({', '.join(filter_msg)})" if filter_msg else ""

    # Step 1: Query expansion
    print(f"Step 1: Expanding query with related technical terms...")

    # Step 2: Hybrid search (vector + BM25)
    print(f"Step 2: Hybrid search{filter_str} (retrieving {N_CANDIDATES} candidates)...")

    # Step 3: Reranking to get top 5
    print(f"Step 3: Reranking by relevance (selecting top {TOP_K})...")

    try:
        # Use the improved retrieval pipeline from lib.rag
        chunks = rag.retrieve_with_hybrid_and_reranking(
            question=question,
            api_key=api_key,
            top_k=TOP_K,
            n_candidates=N_CANDIDATES,
            alpha=ALPHA,
            filter_chemistry=filter_chemistry,
            filter_topic=filter_topic,
            filter_paper_type=filter_paper_type,
            enable_query_expansion=True,
            enable_reranking=True
        )

        if not chunks:
            print("\nNo relevant passages found.")
            if filter_chemistry or filter_topic or filter_paper_type:
                print("Try removing filters or using different filter values.")
            return

        # Print the final chunks
        print(f"\nFinal top {len(chunks)} passages:")
        for i, chunk in enumerate(chunks, 1):
            section_info = f" - {chunk['section_name']}" if chunk.get('section_name', 'Content') != 'Content' else ""
            print(f"  [{i}] {chunk['filename']} (page {chunk['page_num']}){section_info}")

        # Step 4: Query Claude with the reranked chunks
        print(f"\nStep 4: Querying Claude for final answer...")
        answer = rag.query_claude(question, chunks, api_key)

        # Display results
        print("\n" + "="*60)
        print("ANSWER:")
        print("="*60)
        print(answer)

        print("\n" + "-"*60)
        print("SOURCES:")
        print("-"*60)
        print(format_citations(chunks))
        print()

    except Exception as e:
        print(f"\nERROR: Query failed: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Query battery research papers using improved RAG pipeline (hybrid search + reranking)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python query.py "What causes battery degradation?"
  python query.py --chemistry NMC "What is lithium plating?"
  python query.py --topic SOH "How to estimate state of health?"
  python query.py --chemistry LFP --topic degradation "Degradation in LFP cells"

Features:
  - Query expansion: Automatically expands queries with related technical terms
  - Hybrid search: Combines semantic (vector) + keyword (BM25) search
  - Reranking: Retrieves 15 candidates, reorders by relevance, returns top 5
        """
    )
    parser.add_argument('question', nargs='*', help='Question to ask (if not provided, enters interactive mode)')
    parser.add_argument('--chemistry', '-c', help='Filter by chemistry (e.g., NMC, LFP, NCA)')
    parser.add_argument('--topic', '-t', help='Filter by topic (e.g., degradation, SOH, RUL)')
    parser.add_argument('--paper-type', '-p', help='Filter by paper type (e.g., experimental, review)')

    args = parser.parse_args()

    print("\n" + "="*60)
    print("Battery Research Papers RAG - Query Tool")
    print("(Improved with hybrid search + reranking)")
    print("="*60 + "\n")

    # Get API key
    api_key = get_api_key()

    # Verify database exists
    print("Checking database...")
    try:
        count = rag.get_collection_count()
        print(f"  Found {count} documents in database\n")
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

    # Check if question provided as argument
    filter_chemistry = args.chemistry
    filter_topic = args.topic
    filter_paper_type = args.paper_type

    if args.question:
        question = ' '.join(args.question)
        print(f"Question: {question}\n")
        if filter_chemistry:
            print(f"Filter - Chemistry: {filter_chemistry}")
        if filter_topic:
            print(f"Filter - Topic: {filter_topic}")
        if filter_paper_type:
            print(f"Filter - Paper Type: {filter_paper_type}")
        print()
        process_question(question, api_key, filter_chemistry, filter_topic, filter_paper_type)
    else:
        # Interactive mode
        if filter_chemistry or filter_topic or filter_paper_type:
            print("Note: Filters are only supported in single-question mode")
            print("Entering interactive mode without filters\n")
        interactive_mode(api_key)


if __name__ == "__main__":
    main()
