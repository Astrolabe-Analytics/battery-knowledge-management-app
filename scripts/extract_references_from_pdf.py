"""
Extract references from parsed PDF chunks for a paper.
"""
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"

def extract_references_from_chunks(filename: str):
    """Extract references from parsed PDF chunks."""
    print(f"Extracting references from PDF: {filename}")
    print("=" * 70)

    # Load chunks
    chunks_dir = BASE_DIR / "data" / "chunks"
    base_name = filename.replace('.pdf', '')
    chunks_file = chunks_dir / f"{base_name}_chunks.json"

    if not chunks_file.exists():
        print("Chunks file not found")
        return []

    with open(chunks_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        chunks = data.get('chunks', [])

    # Find reference sections
    ref_chunks = [c for c in chunks if 'reference' in c.get('section_name', '').lower()]

    if not ref_chunks:
        print("No reference sections found in PDF")
        return []

    print(f"Found {len(ref_chunks)} reference chunks")

    # Combine all reference text
    ref_text = '\n'.join([c['text'] for c in ref_chunks])

    # Parse references - look for numbered references like [1], [2], etc.
    # Pattern: [number] followed by text until next [number] or end
    pattern = r'\[(\d+)\]\s*(.*?)(?=\[\d+\]|$)'
    matches = re.findall(pattern, ref_text, re.DOTALL)

    references = []
    for ref_num, ref_text in matches:
        ref_text = ref_text.strip()

        if not ref_text or len(ref_text) < 20:
            continue

        # Try to extract components (simplified parsing)
        ref_data = {
            'key': f'ref_{ref_num}',
            'unstructured': ref_text[:500]  # First 500 chars
        }

        # Try to extract title (usually first part before comma or period)
        # Try to extract authors (before title)
        # Try to extract DOI
        doi_match = re.search(r'https?://doi\.org/(10\.\S+)', ref_text)
        if doi_match:
            ref_data['DOI'] = doi_match.group(1)

        # Try to extract year
        year_match = re.search(r'\((\d{4})\)', ref_text)
        if year_match:
            ref_data['year'] = year_match.group(1)

        # Extract title (rough heuristic - text before journal/year)
        # This is simplified - full parsing would need a proper citation parser
        parts = ref_text.split(',')
        if len(parts) >= 2:
            # Assume format: Authors, Title, Journal, Year
            ref_data['article-title'] = parts[1].strip()[:200]

        references.append(ref_data)

    print(f"Extracted {len(references)} references")
    return references

def main():
    filename = "10_1016_j_jpowsour_2022_231127.pdf"

    # Extract references
    references = extract_references_from_chunks(filename)

    if not references:
        print("No references extracted")
        return

    # Load metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    if filename not in metadata:
        print("Paper not in metadata.json")
        return

    # Update metadata
    metadata[filename]['references'] = references

    # Save
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\nUpdated metadata.json with {len(references)} references")

    # Show first 3
    print("\nFirst 3 references:")
    for i, ref in enumerate(references[:3], 1):
        title = ref.get('article-title', ref.get('unstructured', 'No title')[:80])
        print(f"  {i}. {title}...")

if __name__ == "__main__":
    main()
