#!/usr/bin/env python3
"""
Query script for battery research papers RAG system.
Accepts questions and returns answers with citations from the papers.
"""

import os
import sys
import argparse
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer
from anthropic import Anthropic

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


# Configuration
DB_DIR = Path(__file__).parent.parent / "data" / "chroma_db"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "battery_papers"
TOP_K = 5  # Number of chunks to retrieve
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"


def get_api_key() -> str:
    """Get Anthropic API key from environment."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\nERROR: ANTHROPIC_API_KEY environment variable not set")
        print("Please set it with: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)
    return api_key


def load_collection():
    """Load ChromaDB collection."""
    print("Loading database...")

    if not DB_DIR.exists():
        print(f"\nERROR: Database not found at {DB_DIR}")
        print("Please run ingest.py first to create the database")
        sys.exit(1)

    try:
        client = chromadb.PersistentClient(path=str(DB_DIR))
        collection = client.get_collection(name=COLLECTION_NAME)
        count = collection.count()
        print(f"  Loaded collection with {count} documents")
        return collection
    except Exception as e:
        print(f"\nERROR: Failed to load collection: {e}")
        print("Please run ingest.py first to create the database")
        sys.exit(1)


def retrieve_relevant_chunks(collection, question: str, model: SentenceTransformer,
                            filter_chemistry: str = None, filter_topic: str = None) -> list[dict]:
    """
    Retrieve top-K relevant chunks for the question.
    Returns list of dicts with 'text', 'filename', 'page_num'.

    Args:
        collection: ChromaDB collection
        question: User question
        model: Embedding model
        filter_chemistry: Optional chemistry filter (e.g., "NMC", "LFP")
        filter_topic: Optional topic filter (e.g., "degradation", "SOH")
    """
    filter_msg = []
    if filter_chemistry:
        filter_msg.append(f"chemistry={filter_chemistry}")
    if filter_topic:
        filter_msg.append(f"topic={filter_topic}")

    filter_str = f" ({', '.join(filter_msg)})" if filter_msg else ""
    print(f"Searching for relevant passages{filter_str} (top {TOP_K})...")

    # Embed the question
    question_embedding = model.encode([question])[0].tolist()

    # Query ChromaDB - get more results than needed for post-filtering
    # ChromaDB doesn't support substring matching, so we'll filter in Python
    n_results = TOP_K * 10 if (filter_chemistry or filter_topic) else TOP_K

    try:
        results = collection.query(
            query_embeddings=[question_embedding],
            n_results=n_results
        )
    except Exception as e:
        print(f"\nERROR: Failed to query database: {e}")
        sys.exit(1)

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

            # Apply filters (post-filtering since ChromaDB doesn't support substring matching)
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
                'topics': topics,
                'application': metadata.get('application', 'general'),
                'paper_type': metadata.get('paper_type', 'experimental')
            }
            chunks.append(chunk)

            # Only print and keep top K
            if len(chunks) > TOP_K:
                break

    # Print the chunks we're using
    for i, chunk in enumerate(chunks[:TOP_K], 1):
        section_info = f" - {chunk['section_name']}" if chunk['section_name'] != 'Content' else ""
        print(f"  [{i}] {chunk['filename']} (page {chunk['page_num']}){section_info}")

    return chunks[:TOP_K]


def query_claude(question: str, chunks: list[dict], api_key: str) -> str:
    """
    Send question + context to Claude and get answer.
    """
    print(f"\nQuerying Claude ({CLAUDE_MODEL})...")

    # Build context from chunks
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        section_info = f", section: {chunk['section_name']}" if chunk.get('section_name') and chunk['section_name'] != 'Content' else ""
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
        client = Anthropic(api_key=api_key)

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        answer = response.content[0].text
        return answer

    except Exception as e:
        print(f"\nERROR: Failed to query Claude API: {e}")
        sys.exit(1)


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


def interactive_mode(collection, model: SentenceTransformer, api_key: str):
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
            process_question(question, collection, model, api_key)

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except EOFError:
            print("\n\nGoodbye!")
            break


def process_question(question: str, collection, model: SentenceTransformer, api_key: str,
                    filter_chemistry: str = None, filter_topic: str = None):
    """Process a single question."""
    # Retrieve relevant chunks
    chunks = retrieve_relevant_chunks(collection, question, model, filter_chemistry, filter_topic)

    if not chunks:
        print("\nNo relevant passages found.")
        if filter_chemistry or filter_topic:
            print("Try removing filters or using different filter values.")
        return

    # Query Claude
    answer = query_claude(question, chunks, api_key)

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


def main():
    """Main entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Query battery research papers using RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python query.py "What causes battery degradation?"
  python query.py --chemistry NMC "What is lithium plating?"
  python query.py --topic SOH "How to estimate state of health?"
  python query.py --chemistry LFP --topic degradation "Degradation in LFP cells"
        """
    )
    parser.add_argument('question', nargs='*', help='Question to ask (if not provided, enters interactive mode)')
    parser.add_argument('--chemistry', '-c', help='Filter by chemistry (e.g., NMC, LFP, NCA)')
    parser.add_argument('--topic', '-t', help='Filter by topic (e.g., degradation, SOH, RUL)')

    args = parser.parse_args()

    print("\n" + "="*60)
    print("Battery Research Papers RAG - Query Tool")
    print("="*60 + "\n")

    # Get API key
    api_key = get_api_key()

    # Load embedding model
    print("Loading embedding model...")
    try:
        model = SentenceTransformer(EMBEDDING_MODEL)
        print("  Model loaded successfully")
    except Exception as e:
        print(f"\nERROR: Failed to load embedding model: {e}")
        sys.exit(1)

    # Load collection
    collection = load_collection()

    # Check if question provided as argument
    filter_chemistry = args.chemistry
    filter_topic = args.topic

    if args.question:
        question = ' '.join(args.question)
        print(f"\nQuestion: {question}\n")
        if filter_chemistry:
            print(f"Filter - Chemistry: {filter_chemistry}")
        if filter_topic:
            print(f"Filter - Topic: {filter_topic}")
        print()
        process_question(question, collection, model, api_key, filter_chemistry, filter_topic)
    else:
        # Interactive mode
        if filter_chemistry or filter_topic:
            print("Note: Filters are only supported in single-question mode")
            print("Entering interactive mode without filters\n")
        interactive_mode(collection, model, api_key)


if __name__ == "__main__":
    main()
