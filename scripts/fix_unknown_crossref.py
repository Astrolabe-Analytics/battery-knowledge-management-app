"""
Fix papers marked "Unknown - needs manual review" using CrossRef API with PII codes.

CrossRef has excellent coverage of Elsevier/ScienceDirect papers via their alternative-id field.
This should work much better than Semantic Scholar for these papers.
"""

import json
import re
import time
from pathlib import Path
import sys
import io
import requests

# Fix console encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def extract_pii_from_url(url: str) -> str:
    """
    Extract PII (Publisher Item Identifier) from ScienceDirect URL.

    Examples:
        https://www.sciencedirect.com/science/article/pii/S266654682400048X -> S266654682400048X
        https://www.sciencedirect.com/science/article/abs/pii/S0378775324006967 -> S0378775324006967
    """
    if not url or 'sciencedirect.com' not in url.lower():
        return None

    # Pattern: /pii/SXXXXXXXXXX
    match = re.search(r'/pii/([A-Z0-9]+)', url, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def query_crossref_by_pii(pii: str) -> dict:
    """
    Query CrossRef API using PII as alternative-id filter.

    CrossRef API: https://api.crossref.org/works?filter=alternative-id:{PII}

    Args:
        pii: Publisher Item Identifier (e.g., S266654682400048X)

    Returns:
        Dict with title, authors, year, journal, doi if found, None otherwise
    """
    if not pii:
        return None

    try:
        # CrossRef API endpoint with alternative-id filter
        api_url = f"https://api.crossref.org/works"
        params = {
            'filter': f'alternative-id:{pii}',
            'rows': 1  # Only need the first result
        }

        # Add polite pool headers (recommended by CrossRef)
        headers = {
            'User-Agent': 'BatteryResearchPaperDatabase/1.0 (mailto:research@example.com)'
        }

        response = requests.get(api_url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Check if we got results
            if data.get('message', {}).get('items'):
                item = data['message']['items'][0]

                # Extract metadata
                result = {
                    'title': item.get('title', [''])[0] if item.get('title') else None,
                    'doi': item.get('DOI'),
                    'year': str(item.get('published-print', {}).get('date-parts', [['']])[0][0] or
                               item.get('published-online', {}).get('date-parts', [['']])[0][0] or ''),
                    'journal': item.get('container-title', [''])[0] if item.get('container-title') else '',
                    'authors': []
                }

                # Extract authors
                if item.get('author'):
                    for author in item['author']:
                        given = author.get('given', '')
                        family = author.get('family', '')
                        if given and family:
                            result['authors'].append(f"{given} {family}")
                        elif family:
                            result['authors'].append(family)

                # Only return if we have a title
                if result['title']:
                    return result

        return None

    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.RequestException:
        return None
    except Exception as e:
        print(f"    [ERROR] Exception: {type(e).__name__}: {e}", flush=True)
        return None


def main():
    print("=" * 80, flush=True)
    print("Fixing Unknown Titles Using CrossRef API (PII Method)", flush=True)
    print("=" * 80, flush=True)
    print(flush=True)

    # Load metadata
    metadata_file = Path("data/metadata.json")
    if not metadata_file.exists():
        print("[ERROR] metadata.json not found", flush=True)
        return

    with open(metadata_file, 'r', encoding='utf-8') as f:
        all_metadata = json.load(f)

    print(f"Loaded {len(all_metadata)} papers from metadata.json", flush=True)
    print(flush=True)

    # Find papers marked "Unknown - needs manual review"
    unknown_papers = []
    for filename, paper in all_metadata.items():
        title = paper.get('title', '')
        if title == "Unknown - needs manual review":
            unknown_papers.append((filename, paper))

    print(f"Found {len(unknown_papers)} papers marked 'Unknown - needs manual review'", flush=True)
    print(flush=True)

    if len(unknown_papers) == 0:
        print("[OK] No papers need fixing!", flush=True)
        return

    # Process each paper
    fixed_count = 0
    no_pii_count = 0
    not_found_count = 0

    for idx, (filename, paper) in enumerate(unknown_papers, 1):
        print(f"[{idx}/{len(unknown_papers)}] {filename}", flush=True)

        url = paper.get('url') or paper.get('source_url', '')

        # Extract PII from URL
        pii = extract_pii_from_url(url)

        if not pii:
            print(f"  [SKIP] No PII found in URL: {url[:60] if url else 'N/A'}...", flush=True)
            no_pii_count += 1
        else:
            print(f"  [PII] {pii}", flush=True)

            # Query CrossRef
            result = query_crossref_by_pii(pii)

            if result and result.get('title'):
                # Update metadata with all fields
                paper['title'] = result['title']

                if result.get('doi'):
                    paper['doi'] = result['doi']

                if result.get('authors'):
                    paper['authors'] = result['authors']

                if result.get('year'):
                    paper['year'] = result['year']

                if result.get('journal'):
                    paper['journal'] = result['journal']

                fixed_count += 1
                print(f"  [+] FOUND: {result['title'][:70]}...", flush=True)
                if result.get('doi'):
                    print(f"      DOI: {result['doi']}", flush=True)
                if result.get('authors'):
                    print(f"      Authors: {', '.join(result['authors'][:3])}{'...' if len(result['authors']) > 3 else ''}", flush=True)
            else:
                not_found_count += 1
                print(f"  [-] Not found in CrossRef", flush=True)

            # Rate limit: 1 request per second (CrossRef polite pool recommendation)
            time.sleep(1)

        print(flush=True)

        # Save checkpoint every 50 papers
        if idx % 50 == 0:
            print(f"  [+] Checkpoint save at {idx}/{len(unknown_papers)}", flush=True)
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(all_metadata, f, indent=2, ensure_ascii=False)
            print(flush=True)

    # Final save
    print("=" * 80, flush=True)
    print("Saving changes...", flush=True)
    print(flush=True)

    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, indent=2, ensure_ascii=False)

    print("[+] Saved metadata.json", flush=True)

    # Update ChromaDB
    print("[+] Updating ChromaDB...", flush=True)

    # Import DatabaseClient only when needed (avoid slow startup)
    from lib.rag import DatabaseClient

    update_count = 0
    error_count = 0

    for filename, paper in unknown_papers:
        try:
            if paper['title'] != "Unknown - needs manual review":
                success = DatabaseClient.update_paper_metadata(filename, all_metadata[filename])
                if success:
                    update_count += 1
                else:
                    error_count += 1
        except Exception as e:
            error_count += 1
            print(f"  [WARN] ChromaDB update failed for {filename}: {e}", flush=True)

    print(f"[+] Updated {update_count} papers in ChromaDB", flush=True)
    if error_count > 0:
        print(f"[WARN] {error_count} ChromaDB updates failed (likely empty list metadata)", flush=True)

    # Clear caches
    DatabaseClient.clear_cache()
    print("[+] Cleared caches", flush=True)

    # Summary
    print(flush=True)
    print("=" * 80, flush=True)
    print("SUMMARY", flush=True)
    print("=" * 80, flush=True)
    print(f"Papers to process:            {len(unknown_papers)}", flush=True)
    print(f"Successfully fixed:           {fixed_count} ({fixed_count/len(unknown_papers)*100:.1f}%)", flush=True)
    print(f"No PII in URL:                {no_pii_count} ({no_pii_count/len(unknown_papers)*100:.1f}%)", flush=True)
    print(f"Not found in CrossRef:        {not_found_count} ({not_found_count/len(unknown_papers)*100:.1f}%)", flush=True)
    print(f"Still unknown:                {no_pii_count + not_found_count}", flush=True)
    print(flush=True)

    remaining = no_pii_count + not_found_count
    if remaining > 0:
        print(f"[NOTE] {remaining} papers still marked 'Unknown - needs manual review'", flush=True)
        print("These papers either:", flush=True)
        print("  - Don't have a PII in the URL (non-ScienceDirect)", flush=True)
        print("  - Aren't indexed in CrossRef yet", flush=True)
        print("  - Require manual review", flush=True)
        print(flush=True)

    print("[OK] Done! Restart the Streamlit app to see changes.", flush=True)


if __name__ == "__main__":
    main()
