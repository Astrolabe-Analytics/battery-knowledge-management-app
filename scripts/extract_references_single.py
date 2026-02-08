"""
Extract references for a single paper using CrossRef API.
"""
import json
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.app_helpers import enrich_from_crossref

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"

def extract_references(filename: str):
    """Extract references for a paper using CrossRef."""
    print(f"Extracting references for: {filename}")
    print("=" * 70)

    # Load metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    if filename not in metadata:
        print(f"Paper not found in metadata.json")
        return

    paper = metadata[filename]
    doi = paper.get('doi', '')

    if not doi:
        print("No DOI found - cannot extract references from CrossRef")
        return

    print(f"Title: {paper.get('title', 'Unknown')}")
    print(f"DOI: {doi}")
    print()

    # Query CrossRef
    print("Querying CrossRef API...")
    time.sleep(1)  # Rate limiting

    # Build canonical_data dict as expected by enrich_from_crossref
    canonical_data = {
        'doi': doi,
        'url': '',
        'title': paper.get('title', ''),
        'authors': paper.get('authors', []),
        'year': paper.get('year', ''),
        'journal': paper.get('journal', '')
    }

    crossref_data = enrich_from_crossref(canonical_data)

    if not crossref_data:
        print("CrossRef query failed")
        return

    # Check if references exist
    references = crossref_data.get('references', [])

    if not references:
        print("No references found in CrossRef response")
        print("This paper might not have references indexed by CrossRef")
        return

    print(f"Found {len(references)} references!")

    # Update metadata
    paper['references'] = references

    # Save
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\nUpdated metadata.json with {len(references)} references")
    print("\nFirst 3 references:")
    for i, ref in enumerate(references[:3], 1):
        title = ref.get('article-title', ref.get('unstructured', 'No title'))
        print(f"  {i}. {title[:80]}...")

if __name__ == "__main__":
    filename = "10_1016_j_jpowsour_2022_231127.pdf"
    extract_references(filename)
