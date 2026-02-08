"""
Generate AI summaries for the first 5 selected papers.
"""
import json
import os
from pathlib import Path
from typing import Dict, List
import anthropic
import time

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"
SELECTED_PAPERS_FILE = BASE_DIR / "data" / "selected_papers_for_summary.json"

# Claude API setup
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def load_paper_chunks(filename: str) -> List[str]:
    """Load parsed chunks for a paper from chunks directory."""
    chunks_dir = BASE_DIR / "data" / "chunks"
    base_name = filename.replace('.pdf', '')
    chunks_file = chunks_dir / f"{base_name}_chunks.json"

    if chunks_file.exists():
        with open(chunks_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and 'chunks' in data:
                return [chunk.get('text', '') for chunk in data['chunks']]
            elif isinstance(data, list):
                return [chunk.get('text', '') if isinstance(chunk, dict) else str(chunk) for chunk in data]

    return []


def extract_abstract_from_chunks(chunks: List[str]) -> str:
    """Extract abstract from paper chunks."""
    for idx, chunk in enumerate(chunks[:10]):
        chunk_lower = chunk.lower()

        if 'abstract' in chunk_lower[:200]:
            abstract_start = chunk_lower.find('abstract')
            content = chunk[abstract_start:].strip()

            if content.lower().startswith('abstract'):
                content = content[8:].strip()

            content = content.lstrip(':.-— \n\t')

            if 100 < len(content) < 2000:
                return content

    # Fallback
    if chunks and len(chunks[0]) > 100:
        return chunks[0][:1000]

    return ""


def generate_ai_summary(paper_metadata: Dict, abstract: str, full_text_chunks: List[str]) -> str:
    """Generate AI summary using Claude API."""
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

    return response.content[0].text


def main():
    print("=" * 70)
    print("GENERATING AI SUMMARIES FOR FIRST 5 PAPERS")
    print("=" * 70)

    # Load metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Load selected papers
    with open(SELECTED_PAPERS_FILE, 'r', encoding='utf-8') as f:
        selected_filenames = json.load(f)

    # Process first 5 papers
    papers_to_process = selected_filenames[:5]

    print(f"\nProcessing {len(papers_to_process)} papers...\n")

    for idx, filename in enumerate(papers_to_process, 1):
        print(f"[{idx}/5] Processing: {filename}")

        if filename not in metadata:
            print(f"  X Not found in metadata.json, skipping")
            continue

        paper_metadata = metadata[filename]
        title = paper_metadata.get('title', filename)
        print(f"  Title: {title[:80]}...")

        # Load chunks
        chunks = load_paper_chunks(filename)
        if not chunks:
            print(f"  X No chunks found, skipping")
            continue

        print(f"  OK Loaded {len(chunks)} chunks")

        # Extract abstract
        abstract = extract_abstract_from_chunks(chunks)
        print(f"  OK Extracted abstract ({len(abstract)} chars)")

        # Generate AI summary
        print(f"  -> Generating AI summary...")
        try:
            ai_summary = generate_ai_summary(paper_metadata, abstract, chunks)
            print(f"  OK Generated summary ({len(ai_summary)} chars)")

            # Update metadata
            metadata[filename]['abstract'] = abstract
            metadata[filename]['ai_summary'] = ai_summary
            metadata[filename]['summary_generated_at'] = '2026-02-08'
            metadata[filename]['summary_model'] = 'claude-sonnet-4-5-20250929'

            print(f"  OK Updated metadata.json")

        except Exception as e:
            print(f"  X Error generating summary: {e}")
            continue

        # Small delay to respect rate limits
        if idx < len(papers_to_process):
            time.sleep(1)

        print()

    # Save updated metadata
    print("=" * 70)
    print("Saving updated metadata.json...")
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print("OK Done! Updated metadata.json with AI summaries.")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Run: python scripts/mark_incomplete_metadata.py")
    print("   (This will set pdf_status='summarized' for papers with ai_summary)")
    print("2. Run: python scripts/sync_status_to_chromadb.py")
    print("   (This will sync the status to ChromaDB)")
    print("3. Restart the Streamlit app to see the new 'Summarized' status tier")


if __name__ == "__main__":
    main()
