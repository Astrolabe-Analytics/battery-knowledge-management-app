"""
Fix abstracts for the 5 summarized papers - extract proper abstracts from chunks.
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"
SELECTED_PAPERS_FILE = BASE_DIR / "data" / "selected_papers_for_summary.json"

def load_paper_chunks(filename: str):
    """Load chunks for a paper."""
    chunks_dir = BASE_DIR / "data" / "chunks"
    base_name = filename.replace('.pdf', '')
    chunks_file = chunks_dir / f"{base_name}_chunks.json"

    if chunks_file.exists():
        with open(chunks_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and 'chunks' in data:
                return [chunk.get('text', '') for chunk in data['chunks']]
    return []

def extract_better_abstract(chunks):
    """
    Better abstract extraction - look for:
    1. A chunk with 'abstract' or 'Abstract' in it
    2. Extract text AFTER the abstract keyword
    3. Stop at common section headers like Introduction, Keywords, etc.
    """
    for chunk in chunks[:15]:  # Check more chunks
        chunk_lower = chunk.lower()

        # Look for abstract keyword
        if 'abstract' in chunk_lower:
            # Find where "abstract" appears
            abstract_idx = chunk_lower.find('abstract')

            # Get text after "abstract"
            after_abstract = chunk[abstract_idx:].strip()

            # Skip the word "Abstract" itself and any formatting
            lines = after_abstract.split('\n')
            content_lines = []

            found_content = False
            for line in lines:
                line_clean = line.strip()

                # Skip the "Abstract" header line
                if line_clean.lower() in ['abstract', 'abstract:', '**abstract**']:
                    found_content = True
                    continue

                # Stop at common section headers
                if found_content and line_clean.lower().startswith(('introduction', 'keywords', '1.', 'i.', '1 introduction')):
                    break

                # Skip author affiliations (lines with emails, institutions)
                if '@' in line_clean or 'laboratory' in line_clean.lower() or 'university' in line_clean.lower():
                    continue

                # Add actual content
                if found_content and line_clean and len(line_clean) > 20:
                    content_lines.append(line_clean)

            if content_lines:
                abstract = ' '.join(content_lines)
                # Clean up excess whitespace
                abstract = ' '.join(abstract.split())

                if 100 < len(abstract) < 2000:
                    return abstract

    return None

def main():
    print("Fixing abstracts for summarized papers...")
    print("=" * 70)

    # Load metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Load selected papers (first 5 are the ones we summarized)
    with open(SELECTED_PAPERS_FILE, 'r', encoding='utf-8') as f:
        selected = json.load(f)[:5]

    fixed_count = 0

    for filename in selected:
        print(f"\n{filename}:")

        if filename not in metadata:
            print("  Not in metadata.json")
            continue

        # Load chunks
        chunks = load_paper_chunks(filename)
        if not chunks:
            print("  No chunks found")
            continue

        print(f"  Loaded {len(chunks)} chunks")

        # Extract better abstract
        better_abstract = extract_better_abstract(chunks)

        if better_abstract:
            old_abstract = metadata[filename].get('abstract', '')
            print(f"  Old abstract ({len(old_abstract)} chars): {old_abstract[:100]}...")
            print(f"  New abstract ({len(better_abstract)} chars): {better_abstract[:100]}...")

            metadata[filename]['abstract'] = better_abstract
            fixed_count += 1
            print("  Updated!")
        else:
            print("  Could not extract better abstract")

    # Save
    if fixed_count > 0:
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"\n{'=' * 70}")
        print(f"Fixed {fixed_count} abstracts")
        print("Updated metadata.json")
    else:
        print("\nNo abstracts were fixed")

if __name__ == "__main__":
    main()
