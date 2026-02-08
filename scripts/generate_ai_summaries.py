"""
Extract abstracts and generate AI summaries for selected papers.
Uses Claude API to generate structured summaries.
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import anthropic

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"
SELECTED_PAPERS_FILE = BASE_DIR / "data" / "selected_papers_for_summary.json"
CHROMA_DB_DIR = BASE_DIR / "data" / "chroma_db"

# Claude API setup
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def load_paper_chunks(filename: str) -> List[str]:
    """Load parsed chunks for a paper from chunks directory."""
    # Chunks are stored as {filename}_chunks.json in data/chunks/
    chunks_dir = BASE_DIR / "data" / "chunks"

    # Remove .pdf extension and add _chunks.json
    base_name = filename.replace('.pdf', '')
    chunks_file = chunks_dir / f"{base_name}_chunks.json"

    if chunks_file.exists():
        with open(chunks_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Structure is {"filename": "...", "chunks": [...]}
            if isinstance(data, dict) and 'chunks' in data:
                return [chunk.get('text', '') for chunk in data['chunks']]
            # Fallback for list format
            elif isinstance(data, list):
                return [chunk.get('text', '') if isinstance(chunk, dict) else str(chunk) for chunk in data]

    return []


def extract_abstract_from_chunks(chunks: List[str]) -> str:
    """Extract abstract from paper chunks.

    Strategy: Look for chunks that:
    1. Contain the word "abstract" in first 200 chars
    2. Are longer than 100 chars but shorter than 2000 chars
    3. Usually appear in the first 5 chunks
    """
    for idx, chunk in enumerate(chunks[:10]):  # Check first 10 chunks
        chunk_lower = chunk.lower()

        # Look for abstract markers
        if 'abstract' in chunk_lower[:200]:
            # Extract text after "abstract" keyword
            abstract_start = chunk_lower.find('abstract')

            # Skip to content after the word "abstract"
            content = chunk[abstract_start:].strip()

            # Remove "Abstract" header itself
            if content.lower().startswith('abstract'):
                content = content[8:].strip()

            # Remove leading punctuation/whitespace
            content = content.lstrip(':.-— \n\t')

            # If it's a reasonable length, return it
            if 100 < len(content) < 2000:
                return content

    # Fallback: use first chunk if no abstract found
    if chunks and len(chunks[0]) > 100:
        return chunks[0][:1000]  # First 1000 chars

    return ""


def generate_ai_summary(paper_metadata: Dict, abstract: str, full_text_chunks: List[str]) -> Dict:
    """Generate AI summary using Claude API.

    Returns structured summary with:
    - 2-3 sentence overview
    - Key findings (3-5 bullet points)
    - Methods (2-3 bullet points)
    - Novel contributions
    """

    # Combine first few chunks for context (limit to ~10k chars)
    context_text = "\n\n".join(full_text_chunks[:5])[:10000]

    prompt = f"""You are analyzing a battery research paper. Generate a structured summary with the following sections:

PAPER METADATA:
Title: {paper_metadata.get('title', 'Unknown')}
Authors: {'; '.join(paper_metadata.get('authors', [])[:5])}
Journal: {paper_metadata.get('journal', 'Unknown')}
Year: {paper_metadata.get('year', 'Unknown')}
Chemistries: {', '.join(paper_metadata.get('chemistries', []))}

ABSTRACT:
{abstract}

PAPER TEXT (first sections):
{context_text}

Generate a structured summary in the following format:

## Overview
[2-3 sentences summarizing the paper's main focus and contribution]

## Key Findings
- [Finding 1]
- [Finding 2]
- [Finding 3]
[Add up to 5 bullet points of the most important findings]

## Methods
- [Method 1]
- [Method 2]
[2-3 bullet points describing the experimental or computational methods]

## Novel Contributions
[1-2 sentences on what makes this work novel or significant]

Be concise, technical, and focus on the most important aspects. Use battery domain terminology."""

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1500,
        temperature=0,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )

    summary_text = response.content[0].text

    return {
        'ai_summary': summary_text,
        'abstract': abstract,
        'summary_generated_at': '2026-02-08',
        'summary_model': 'claude-sonnet-4-5-20250929'
    }


def main():
    print("=" * 70)
    print("AI SUMMARY GENERATION")
    print("=" * 70)

    # Load metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Load selected papers
    with open(SELECTED_PAPERS_FILE, 'r', encoding='utf-8') as f:
        selected_filenames = json.load(f)

    print(f"\nFound {len(selected_filenames)} selected papers.")

    # Check which papers already have summaries
    papers_with_summaries = []
    papers_without_summaries = []

    for filename in selected_filenames:
        if filename in metadata:
            if metadata[filename].get('ai_summary'):
                papers_with_summaries.append(filename)
            else:
                papers_without_summaries.append(filename)

    print(f"\nPapers with existing summaries: {len(papers_with_summaries)}")
    print(f"Papers needing summaries: {len(papers_without_summaries)}")

    if papers_with_summaries:
        print("\nPapers that already have summaries:")
        for filename in papers_with_summaries:
            print(f"  - {metadata[filename].get('title', filename)}")

    # Generate one example summary
    print("\n" + "=" * 70)
    print("GENERATING EXAMPLE SUMMARY")
    print("=" * 70)

    # Use first paper without summary, or first paper if all have summaries
    example_filename = papers_without_summaries[0] if papers_without_summaries else selected_filenames[0]
    example_metadata = metadata[example_filename]

    print(f"\nExample paper: {example_metadata.get('title')}")
    print(f"File: {example_filename}")

    # Load chunks
    print("\nLoading paper chunks...")
    chunks = load_paper_chunks(example_filename)
    print(f"Loaded {len(chunks)} chunks")

    if not chunks:
        print("ERROR: No chunks found for this paper. Trying another paper...")
        # Try next paper
        for filename in papers_without_summaries[1:]:
            chunks = load_paper_chunks(filename)
            if chunks:
                example_filename = filename
                example_metadata = metadata[filename]
                print(f"Using: {example_metadata.get('title')}")
                break

    if not chunks:
        print("ERROR: Could not load chunks for any selected paper.")
        return

    # Extract abstract
    print("\nExtracting abstract...")
    abstract = extract_abstract_from_chunks(chunks)
    print(f"Abstract length: {len(abstract)} characters")
    print(f"\nExtracted Abstract:\n{abstract[:500]}...")

    # Generate AI summary
    print("\nGenerating AI summary using Claude API...")
    summary_data = generate_ai_summary(example_metadata, abstract, chunks)

    print("\n" + "=" * 70)
    print("GENERATED AI SUMMARY")
    print("=" * 70)
    print(summary_data['ai_summary'])

    print("\n" + "=" * 70)
    print("EXAMPLE COMPLETE")
    print("=" * 70)
    print(f"\nThis summary will be saved to metadata.json as:")
    print(f"  - 'abstract': {len(abstract)} characters")
    print(f"  - 'ai_summary': {len(summary_data['ai_summary'])} characters")
    print(f"  - 'pdf_status': 'summarized' (will be set by mark_incomplete_metadata.py)")

    print("\n" + "=" * 70)
    print(f"Ready to generate summaries for {len(papers_without_summaries)} papers.")
    print("=" * 70)


if __name__ == "__main__":
    main()
