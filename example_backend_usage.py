#!/usr/bin/env python3
"""
Example: Using the RAG backend module directly (without Streamlit UI)

This demonstrates how the backend can be used with any frontend
(CLI, web API, GUI, etc.) without modification.
"""

from lib import rag

# Example 1: Get library overview
print("=" * 60)
print("Example 1: Get all papers in the library")
print("=" * 60)

papers = rag.get_paper_library()
print(f"\nFound {len(papers)} papers:\n")

for paper in papers[:3]:  # Show first 3
    print(f"📄 {paper['filename']}")
    print(f"   Chemistries: {', '.join(paper['chemistries']) if paper['chemistries'] else 'None'}")
    print(f"   Topics: {', '.join(paper['topics'][:3])}...")
    print(f"   Type: {paper['paper_type']}")
    print()


# Example 2: Search for relevant chunks
print("\n" + "=" * 60)
print("Example 2: Search for relevant passages")
print("=" * 60)

question = "What causes battery degradation?"
print(f"\nQuestion: {question}\n")

chunks = rag.retrieve_relevant_chunks(
    question=question,
    top_k=3,
    filter_chemistry="LFP"  # Optional filter
)

print(f"Found {len(chunks)} relevant chunks:\n")

for i, chunk in enumerate(chunks, 1):
    print(f"[{i}] {chunk['filename']}, page {chunk['page_num']}")
    if chunk.get('section_name'):
        print(f"    Section: {chunk['section_name']}")
    print(f"    Preview: {chunk['text'][:150]}...")
    print()


# Example 3: Get answer from Claude (requires API key)
print("\n" + "=" * 60)
print("Example 3: Query Claude for an answer")
print("=" * 60)

api_key = rag.get_api_key_from_env()

if api_key:
    print(f"\nAsking Claude: {question}\n")

    answer = rag.query_claude(question, chunks, api_key)
    print("Answer:")
    print(answer[:500] + "..." if len(answer) > 500 else answer)
else:
    print("\nSkipping - no ANTHROPIC_API_KEY found in environment")


# Example 4: Get filter options
print("\n" + "=" * 60)
print("Example 4: Get available filter options")
print("=" * 60)

filters = rag.get_filter_options()
print(f"\nAvailable chemistries: {', '.join(filters['chemistries'][:5])}...")
print(f"Available topics: {', '.join(filters['topics'][:5])}...")
print(f"Available paper types: {', '.join(filters['paper_types'])}")


# Example 5: Get paper details
print("\n" + "=" * 60)
print("Example 5: Get details for a specific paper")
print("=" * 60)

if papers:
    paper_filename = papers[0]['filename']
    print(f"\nGetting details for: {paper_filename}\n")

    details = rag.get_paper_details(paper_filename)
    if details:
        print(f"Application: {details['application']}")
        print(f"Paper type: {details['paper_type']}")
        print(f"Chemistries: {', '.join(details['chemistries'])}")
        print(f"Preview chunks: {len(details['preview_chunks'])}")


print("\n" + "=" * 60)
print("Examples complete!")
print("=" * 60)
