"""
Extract references for all summarized papers using CrossRef and PDF parsing.
"""
import json
import sys
import time
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.app_helpers import enrich_from_crossref

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"

def extract_from_crossref(doi: str):
    """Try to extract references using CrossRef API."""
    if not doi:
        return []

    print(f"  Trying CrossRef API with DOI: {doi}")
    time.sleep(1)  # Rate limiting

    try:
        canonical_data = {'doi': doi, 'url': '', 'title': '', 'authors': [], 'year': '', 'journal': ''}
        crossref_data = enrich_from_crossref(canonical_data)

        if crossref_data and crossref_data.get('references'):
            refs = crossref_data['references']
            print(f"  Found {len(refs)} references from CrossRef")
            return refs
    except Exception as e:
        print(f"  CrossRef error: {e}")

    return []

def extract_from_pdf_chunks(filename: str):
    """Extract references from parsed PDF chunks."""
    print(f"  Trying PDF chunk extraction")

    chunks_dir = BASE_DIR / "data" / "chunks"
    base_name = filename.replace('.pdf', '')
    chunks_file = chunks_dir / f"{base_name}_chunks.json"

    if not chunks_file.exists():
        print(f"  No chunks file found")
        return []

    with open(chunks_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        chunks = data.get('chunks', [])

    # Find reference sections - try explicit section name first
    ref_chunks = [c for c in chunks if 'reference' in c.get('section_name', '').lower()]

    # If no explicit reference section, look for reference-like content in last 20 chunks
    if not ref_chunks:
        print(f"  No explicit reference section, checking last chunks for citation patterns")
        last_chunks = chunks[-20:] if len(chunks) > 20 else chunks

        for chunk in last_chunks:
            text = chunk.get('text', '')
            # Look for citation patterns: author names, years in parentheses, journal titles
            # Format 1: "[1] Author et al. 2020"
            # Format 2: "Author, A. (2020)" or "A. Author 2020"
            # Format 3: Multiple author names and journals
            if re.search(r'\[[0-9]+\].*?[0-9]{4}', text) or \
               re.search(r'[A-Z][a-z]+,\s*[A-Z]\.\s*.*?\([0-9]{4}\)', text) or \
               re.search(r'[A-Z]\.\s*[A-Z][a-z]+.*?[0-9]{4}', text):
                ref_chunks.append(chunk)

    if not ref_chunks:
        print(f"  No reference sections or citation patterns found in PDF")
        return []

    print(f"  Found {len(ref_chunks)} reference chunks")

    # Combine all reference text
    ref_text = '\n'.join([c['text'] for c in ref_chunks])

    # Parse references - try three formats:
    # Format 1: [1], [2], [3] etc.
    # Format 2: Plain numbers at line start: "1 Author...", "2 Author..."
    # Format 3: Author-year format: "Author, A. (2020). Title. Journal..."

    pattern1 = r'\[(\d+)\]\s*(.*?)(?=\[\d+\]|$)'
    matches = re.findall(pattern1, ref_text, re.DOTALL)

    # If format 1 didn't work, try format 2
    if not matches:
        pattern2 = r'(?:^|\n)(\d+)\s+([A-Z].*?)(?=\n\d+\s+[A-Z]|$)'
        matches = re.findall(pattern2, ref_text, re.DOTALL)

    # If format 2 didn't work, try format 3 (author-year)
    if not matches:
        # Look for pattern: LastName, F. ... (year).
        pattern3 = r'([A-Z][a-z]+,\s*[A-Z]\..*?\(\d{4}\).*?)(?=(?:[A-Z][a-z]+,\s*[A-Z]\.|$))'
        raw_matches = re.findall(pattern3, ref_text, re.DOTALL)
        # Convert to numbered format for consistency
        matches = [(str(i+1), text.strip()) for i, text in enumerate(raw_matches) if len(text.strip()) > 50]

    if not matches:
        print(f"  Could not parse reference format")
        return []

    references = []
    for ref_num, ref_text in matches:
        ref_text = ref_text.strip()

        if not ref_text or len(ref_text) < 20:
            continue

        ref_data = {
            'key': f'ref_{ref_num}',
            'unstructured': ref_text[:500]
        }

        # Try to extract DOI
        doi_match = re.search(r'https?://doi\.org/(10\.\S+)', ref_text)
        if doi_match:
            ref_data['DOI'] = doi_match.group(1)

        # Try to extract year
        year_match = re.search(r'\((\d{4})\)', ref_text)
        if year_match:
            ref_data['year'] = year_match.group(1)

        # Extract title (rough heuristic)
        parts = ref_text.split(',')
        if len(parts) >= 2:
            ref_data['article-title'] = parts[1].strip()[:200]

        references.append(ref_data)

    print(f"  Extracted {len(references)} references from PDF")
    return references

def main():
    print("Extracting references for all summarized papers")
    print("=" * 70)

    # Load metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Find summarized papers
    summarized = [(fn, meta) for fn, meta in metadata.items() if meta.get('pdf_status') == 'summarized']

    print(f"\nFound {len(summarized)} summarized papers\n")

    updated_count = 0

    for filename, paper in summarized:
        title = paper.get('title', 'Unknown')[:60]
        existing_refs = paper.get('references', [])

        print(f"\n{filename}")
        print(f"Title: {title}...")
        print(f"Existing references: {len(existing_refs)}")

        if existing_refs:
            print("  Skipping - already has references")
            continue

        # Try CrossRef first (if DOI exists)
        references = []
        doi = paper.get('doi', '')

        if doi:
            references = extract_from_crossref(doi)

        # If CrossRef failed, try PDF extraction
        if not references:
            references = extract_from_pdf_chunks(filename)

        if references:
            paper['references'] = references
            updated_count += 1
            print(f"  SUCCESS: Added {len(references)} references")
        else:
            print(f"  FAILED: No references found")

    # Save
    if updated_count > 0:
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"\n{'=' * 70}")
        print(f"Updated {updated_count} papers with references")
        print("Saved to metadata.json")
    else:
        print(f"\n{'=' * 70}")
        print("No papers were updated")

if __name__ == "__main__":
    main()
