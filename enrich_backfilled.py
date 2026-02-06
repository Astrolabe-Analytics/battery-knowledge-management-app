"""
Enrich metadata for papers that were just backfilled with URLs
"""
import json
import time
import re
from pathlib import Path

def extract_doi_from_url(url: str) -> str:
    """Extract DOI from various URL formats"""
    if not url:
        return ''

    # Direct DOI URL
    match = re.search(r'doi\.org/(10\.\d+/[^\s]+)', url)
    if match:
        return match.group(1)

    # Embedded in other URLs (e.g., ScienceDirect, IOP, Nature)
    match = re.search(r'(10\.\d+/[^\s\?&]+)', url)
    if match:
        return match.group(1)

    return ''

def query_crossref_for_metadata(doi: str) -> dict:
    """Query CrossRef API for paper metadata"""
    import requests

    if not doi:
        return {}

    try:
        url = f"https://api.crossref.org/works/{doi}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        message = data.get('message', {})

        # Extract metadata
        metadata = {}

        # Title
        if 'title' in message and message['title']:
            metadata['title'] = message['title'][0]

        # Authors
        if 'author' in message:
            authors = []
            for author in message['author']:
                given = author.get('given', '')
                family = author.get('family', '')
                if family:
                    if given:
                        authors.append(f"{family}, {given}")
                    else:
                        authors.append(family)
            metadata['authors'] = authors

        # Year
        if 'published-print' in message:
            date_parts = message['published-print'].get('date-parts', [[]])[0]
            if date_parts:
                metadata['year'] = str(date_parts[0])
        elif 'published-online' in message:
            date_parts = message['published-online'].get('date-parts', [[]])[0]
            if date_parts:
                metadata['year'] = str(date_parts[0])

        # Journal
        if 'container-title' in message and message['container-title']:
            metadata['journal'] = message['container-title'][0]

        # Abstract
        if 'abstract' in message:
            metadata['abstract'] = message['abstract']

        return metadata

    except Exception as e:
        print(f"  ERROR querying CrossRef: {e}")
        return {}

def main():
    # Load backfill results
    results_file = Path("backfill_results.json")
    if not results_file.exists():
        print("ERROR: backfill_results.json not found. Run backfill_urls.py first.")
        return

    with open(results_file, 'r', encoding='utf-8') as f:
        backfilled = json.load(f)

    print(f"Loaded {len(backfilled)} papers that were backfilled with URLs")

    # Load metadata
    metadata_file = Path("data/metadata.json")
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Enrich each backfilled paper
    print("\nEnriching metadata from CrossRef...")
    enriched_count = 0
    after_data = []

    for i, item in enumerate(backfilled, 1):
        filename = item['filename']
        url = item['url']
        paper = metadata.get(filename)

        if not paper:
            continue

        print(f"\n{i}/{len(backfilled)}: {item['title'][:60]}...")

        # Extract DOI
        doi = paper.get('doi', '')
        if not doi:
            doi = extract_doi_from_url(url)
            if doi:
                print(f"  Extracted DOI: {doi}")
                paper['doi'] = doi

        # Query CrossRef
        if doi:
            crossref_data = query_crossref_for_metadata(doi)

            if crossref_data:
                # Update missing fields only
                updated_fields = []

                if not paper.get('authors') or paper.get('authors') == []:
                    if crossref_data.get('authors'):
                        paper['authors'] = crossref_data['authors']
                        updated_fields.append('authors')

                if not paper.get('year'):
                    if crossref_data.get('year'):
                        paper['year'] = crossref_data['year']
                        updated_fields.append('year')

                if not paper.get('journal'):
                    if crossref_data.get('journal'):
                        paper['journal'] = crossref_data['journal']
                        updated_fields.append('journal')

                if not paper.get('abstract'):
                    if crossref_data.get('abstract'):
                        paper['abstract'] = crossref_data['abstract']
                        updated_fields.append('abstract')

                if updated_fields:
                    print(f"  Updated: {', '.join(updated_fields)}")
                    enriched_count += 1
                else:
                    print(f"  No updates needed")

                # Save after state for comparison
                after_data.append({
                    'filename': filename,
                    'title': paper.get('title', ''),
                    'after': {k: v for k, v in paper.items() if k in ['title', 'authors', 'year', 'journal', 'source_url', 'doi', 'abstract']}
                })
            else:
                print(f"  No CrossRef data found")

        # Rate limiting
        time.sleep(1.0)

    # Save updated metadata
    if enriched_count > 0:
        print(f"\nSaving updated metadata...")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"Saved")

    # Save after results
    with open('enrichment_after.json', 'w', encoding='utf-8') as f:
        json.dump(after_data, f, indent=2, ensure_ascii=False)

    print(f"\nEnrichment complete! Updated {enriched_count} of {len(backfilled)} papers")
    print(f"Saved after results to: enrichment_after.json")

if __name__ == '__main__':
    main()
