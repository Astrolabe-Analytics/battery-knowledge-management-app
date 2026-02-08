"""
Enrich a single paper with missing metadata using Semantic Scholar and CrossRef APIs.
"""
import json
import time
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.semantic_scholar import search_papers
from lib.app_helpers import enrich_from_crossref

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"

def enrich_paper(filename: str):
    """Try to enrich a single paper."""
    print(f"Enriching: {filename}")
    print("=" * 70)

    # Load metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    if filename not in metadata:
        print(f"Paper {filename} not found in metadata.json")
        return

    paper = metadata[filename]
    title = paper.get('title', '')
    authors = paper.get('authors', [])
    year = paper.get('year', '')

    print(f"Title: {title}")
    print(f"Authors: {'; '.join(authors) if isinstance(authors, list) else authors}")
    print(f"Year: {year}")
    print(f"Current DOI: {paper.get('doi', 'None')}")
    print(f"Current Journal: {paper.get('journal', 'Unknown')}")
    print()

    # Try Semantic Scholar first
    print("Searching Semantic Scholar...")
    response = search_papers(title, sort="relevance")

    if response.get('success') and response.get('data') and len(response['data']) > 0:
        result = response['data'][0]  # Take first result
        print(f"Found on Semantic Scholar!")
        print(f"  Paper ID: {result.get('paperId', 'N/A')}")

        # Get DOI if available
        doi = result.get('externalIds', {}).get('DOI')
        if doi:
            print(f"  DOI: {doi}")
            paper['doi'] = doi

            # Now try CrossRef with the DOI
            print(f"\nEnriching from CrossRef using DOI: {doi}")
            time.sleep(1)  # Rate limiting

            crossref_data = enrich_from_crossref(doi)
            if crossref_data:
                print("CrossRef enrichment successful!")

                # Update metadata
                if crossref_data.get('title'):
                    paper['title'] = crossref_data['title']
                    print(f"  Updated title: {crossref_data['title']}")

                if crossref_data.get('journal'):
                    paper['journal'] = crossref_data['journal']
                    print(f"  Updated journal: {crossref_data['journal']}")

                if crossref_data.get('authors'):
                    paper['authors'] = crossref_data['authors']
                    print(f"  Updated authors: {len(crossref_data['authors'])} authors")

                if crossref_data.get('year'):
                    paper['year'] = crossref_data['year']
                    print(f"  Updated year: {crossref_data['year']}")

                # Save updated metadata
                with open(METADATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)

                print("\nMetadata updated successfully!")
                return True
            else:
                print("CrossRef lookup failed")
        else:
            print("  No DOI found in Semantic Scholar")

            # Try to get journal from Semantic Scholar
            journal = result.get('venue')
            if journal:
                paper['journal'] = journal
                print(f"  Got journal from Semantic Scholar: {journal}")

                # Save
                with open(METADATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                print("\nMetadata updated with journal name!")
                return True
    else:
        print("Paper not found on Semantic Scholar")

    return False

if __name__ == "__main__":
    filename = "url_bff78cb4.pdf"
    success = enrich_paper(filename)

    if not success:
        print("\nEnrichment failed - no additional metadata found")
