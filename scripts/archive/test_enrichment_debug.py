"""
Debug metadata enrichment for a specific paper with detailed logging
"""
import json
import re
import requests
from pathlib import Path

def extract_doi_from_url(url: str) -> str:
    """Extract DOI from various URL formats"""
    print(f"\n  [DOI EXTRACTION]")
    print(f"    Input URL: {url}")

    if not url:
        print(f"    Result: EMPTY URL")
        return ''

    # Direct DOI URL
    match = re.search(r'doi\.org/(10\.\d+/[^\s]+)', url)
    if match:
        doi = match.group(1)
        print(f"    Match: doi.org pattern")
        print(f"    Extracted DOI: {doi}")
        return doi

    # Embedded in other URLs (e.g., ScienceDirect, IOP, Nature)
    match = re.search(r'(10\.\d+/[^\s\?&]+)', url)
    if match:
        doi = match.group(1)
        print(f"    Match: embedded DOI pattern")
        print(f"    Extracted DOI: {doi}")
        return doi

    print(f"    Result: NO DOI PATTERN FOUND")
    print(f"    Note: URL does not contain a DOI pattern (10.xxxx/...)")
    return ''

def query_crossref_for_metadata(doi: str) -> dict:
    """Query CrossRef API for paper metadata with detailed logging"""
    print(f"\n  [CROSSREF QUERY]")
    print(f"    DOI: {doi}")

    if not doi:
        print(f"    Result: SKIPPED (no DOI)")
        return {}

    try:
        url = f"https://api.crossref.org/works/{doi}"
        print(f"    API URL: {url}")
        print(f"    Sending request...")

        response = requests.get(url, timeout=10)
        print(f"    Response status: {response.status_code}")

        if response.status_code != 200:
            print(f"    Result: FAILED - HTTP {response.status_code}")
            print(f"    Response text: {response.text[:200]}")
            return {}

        response.raise_for_status()
        data = response.json()

        print(f"    Response JSON keys: {list(data.keys())}")

        if 'message' not in data:
            print(f"    Result: FAILED - No 'message' key in response")
            print(f"    Full response: {json.dumps(data, indent=2)[:500]}")
            return {}

        message = data.get('message', {})
        print(f"    Message keys: {list(message.keys())[:10]}")

        # Extract metadata
        metadata = {}

        # Title
        if 'title' in message and message['title']:
            metadata['title'] = message['title'][0]
            print(f"    ✓ Title: {metadata['title'][:60]}...")

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
            print(f"    ✓ Authors: {len(authors)} author(s)")

        # Year
        if 'published-print' in message:
            date_parts = message['published-print'].get('date-parts', [[]])[0]
            if date_parts:
                metadata['year'] = str(date_parts[0])
                print(f"    ✓ Year (print): {metadata['year']}")
        elif 'published-online' in message:
            date_parts = message['published-online'].get('date-parts', [[]])[0]
            if date_parts:
                metadata['year'] = str(date_parts[0])
                print(f"    ✓ Year (online): {metadata['year']}")

        # Journal
        if 'container-title' in message and message['container-title']:
            metadata['journal'] = message['container-title'][0]
            print(f"    ✓ Journal: {metadata['journal']}")

        # Abstract
        if 'abstract' in message:
            metadata['abstract'] = message['abstract']
            print(f"    ✓ Abstract: {len(message['abstract'])} chars")

        print(f"    Result: SUCCESS - Extracted {len(metadata)} fields")
        return metadata

    except requests.exceptions.Timeout:
        print(f"    Result: FAILED - Request timeout (>10s)")
        return {}
    except requests.exceptions.RequestException as e:
        print(f"    Result: FAILED - Request error: {type(e).__name__}: {e}")
        return {}
    except json.JSONDecodeError as e:
        print(f"    Result: FAILED - JSON decode error: {e}")
        return {}
    except Exception as e:
        print(f"    Result: FAILED - Unexpected error: {type(e).__name__}: {e}")
        import traceback
        print(f"    Traceback: {traceback.format_exc()}")
        return {}

def test_paper_enrichment(filename: str):
    """Test enrichment for a specific paper"""
    print("=" * 80)
    print(f"DETAILED ENRICHMENT TEST")
    print("=" * 80)

    # Load metadata
    metadata_file = Path("data/metadata.json")
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    if filename not in metadata:
        print(f"ERROR: Paper '{filename}' not found in metadata")
        return

    paper = metadata[filename]

    print(f"\n[PAPER INFO]")
    print(f"  Filename: {filename}")
    print(f"  Title: {paper.get('title', 'N/A')}")

    print(f"\n[CURRENT METADATA]")
    print(f"  Authors: {paper.get('authors', 'MISSING')}")
    print(f"  Year: {paper.get('year', 'MISSING')}")
    print(f"  Journal: {paper.get('journal', 'MISSING')}")
    print(f"  DOI: {paper.get('doi', 'MISSING') or 'MISSING'}")
    print(f"  Source URL: {paper.get('source_url', 'MISSING') or 'MISSING'}")

    # Check if needs enrichment
    url = paper.get('url', '') or paper.get('source_url', '')
    doi = paper.get('doi', '')

    missing_authors = not paper.get('authors') or paper.get('authors') == []
    missing_year = not paper.get('year')
    missing_journal = not paper.get('journal')

    print(f"\n[ENRICHMENT NEED ANALYSIS]")
    print(f"  Has URL: {bool(url)}")
    print(f"  Has DOI: {bool(doi)}")
    print(f"  Missing authors: {missing_authors}")
    print(f"  Missing year: {missing_year}")
    print(f"  Missing journal: {missing_journal}")
    print(f"  Needs enrichment: {(url or doi) and (missing_authors or missing_year or missing_journal)}")

    if not (url or doi):
        print(f"\n❌ CANNOT ENRICH: No URL or DOI available")
        return

    if not (missing_authors or missing_year or missing_journal):
        print(f"\n✓ NO ENRICHMENT NEEDED: All metadata complete")
        return

    # Step 1: Extract DOI from URL
    print(f"\n{'='*80}")
    print(f"STEP 1: DOI EXTRACTION")
    print(f"{'='*80}")

    if not doi and url:
        doi = extract_doi_from_url(url)
        if doi:
            print(f"\n  ✓ Extracted DOI: {doi}")
        else:
            print(f"\n  ❌ Could not extract DOI from URL")
            print(f"  This URL format is not supported for DOI extraction")
            print(f"  Supported formats:")
            print(f"    - https://doi.org/10.xxxx/...")
            print(f"    - URLs containing 10.xxxx/... pattern")
    else:
        print(f"  Using existing DOI: {doi}")

    # Step 2: Query CrossRef
    print(f"\n{'='*80}")
    print(f"STEP 2: CROSSREF METADATA QUERY")
    print(f"{'='*80}")

    if not doi:
        print(f"\n  ❌ CANNOT QUERY: No DOI available")
        print(f"  CrossRef requires a DOI to fetch metadata")
        print(f"  For non-DOI URLs (like ChemRxiv), metadata enrichment is not possible via CrossRef")
        return

    crossref_metadata = query_crossref_for_metadata(doi)

    # Step 3: Apply updates
    print(f"\n{'='*80}")
    print(f"STEP 3: METADATA UPDATE")
    print(f"{'='*80}")

    if not crossref_metadata:
        print(f"\n  ❌ NO UPDATES: CrossRef returned no data")
        print(f"  Possible reasons:")
        print(f"    - DOI not found in CrossRef database")
        print(f"    - DOI format incorrect")
        print(f"    - CrossRef API error")
        return

    print(f"\n  Available from CrossRef:")
    for key, value in crossref_metadata.items():
        if isinstance(value, list):
            print(f"    {key}: {len(value)} items")
        else:
            print(f"    {key}: {str(value)[:60]}...")

    updates = []

    if missing_authors and crossref_metadata.get('authors'):
        updates.append(f"authors ({len(crossref_metadata['authors'])} authors)")

    if missing_year and crossref_metadata.get('year'):
        updates.append(f"year ({crossref_metadata['year']})")

    if missing_journal and crossref_metadata.get('journal'):
        updates.append(f"journal ({crossref_metadata['journal']})")

    if updates:
        print(f"\n  ✓ Would update: {', '.join(updates)}")
    else:
        print(f"\n  ℹ No updates needed (fields already exist)")

    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")

    if doi and crossref_metadata and updates:
        print(f"  ✓ Enrichment would SUCCEED")
    elif not doi:
        print(f"  ❌ Enrichment FAILED: No DOI could be extracted from URL")
    elif not crossref_metadata:
        print(f"  ❌ Enrichment FAILED: CrossRef returned no data for DOI")
    elif not updates:
        print(f"  ℹ Enrichment SKIPPED: All fields already complete")

if __name__ == '__main__':
    # Test on "The generalisation challenge..." paper
    test_paper_enrichment("The_generalisation_challenge_assessment_of_the_ef.pdf")
