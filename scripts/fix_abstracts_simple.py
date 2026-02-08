"""
Simple fix: For the 5 summarized papers, use chunk 1 as abstract if chunk 0 has author info.
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"

# Manually specify fixes based on inspection
ABSTRACT_FIXES = {
    "10_1016_j_jpowsour_2022_231127.pdf": {
        "chunk_indices": [1, 2],  # Use chunks 1-2
        "reason": "Chunk 0 has author affiliations"
    }
}

def load_paper_chunks(filename):
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

def main():
    print("Fixing abstracts with manual mappings...")
    print("=" * 70)

    # Load metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    for filename, fix_info in ABSTRACT_FIXES.items():
        print(f"\n{filename}:")

        chunks = load_paper_chunks(filename)
        if not chunks:
            print("  No chunks found")
            continue

        # Get specified chunks
        chunk_indices = fix_info['chunk_indices']
        abstract_parts = [chunks[i] for i in chunk_indices if i < len(chunks)]
        new_abstract = ' '.join(abstract_parts)

        # Clean up
        new_abstract = ' '.join(new_abstract.split())  # Remove excess whitespace

        old_abstract = metadata[filename].get('abstract', '')

        print(f"  Old ({len(old_abstract)} chars): {old_abstract[:80]}...")
        print(f"  New ({len(new_abstract)} chars): {new_abstract[:80]}...")

        metadata[filename]['abstract'] = new_abstract

    # Save
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 70}")
    print("Fixed abstracts")

if __name__ == "__main__":
    main()
