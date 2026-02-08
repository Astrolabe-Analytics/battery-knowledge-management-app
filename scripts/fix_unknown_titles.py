"""
Fix papers marked "Unknown - needs manual review" using Semantic Scholar API.

Attempts to find titles by:
1. Extracting PII from ScienceDirect URLs and searching Semantic Scholar
2. Searching by DOI if present
3. Searching by URL directly
4. Fuzzy title search as fallback
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

# Don't import DatabaseClient here - import it later when needed to avoid slow startup


def extract_pii_from_url(url: str) -> str:
    """
    Extract PII (Publisher Item Identifier) from ScienceDirect URL.

    Examples:
        https://www.sciencedirect.com/science/article/pii/S266654682400048X -> S266654682400048X
        https://www.sciencedirect.com/science/article/abs/pii/S0378775324006967 -> S0378775324006967
    """
    if not url or 'sciencedirect.com' not in url.lower():
        return None

    # Pattern: /pii/SXXXXXXXXXX or /pii/SXXXXXXXXXXX
    match = re.search(r'/pii/([A-Z0-9]+)', url, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def search_semantic_scholar(query: str, query_type: str = "general") -> dict:
    """
    Search Semantic Scholar API for paper metadata.

    Args:
        query: Search query (PII, DOI, URL, or title)
        query_type: Type of query - "pii", "doi", "url", or "general"

    Returns:
        Dict with title, authors, year, journal, doi if found, None otherwise
    """
    try:
        base_url = "https://api.semanticscholar.org/graph/v1/paper"

        # Try different search strategies based on query type
        if query_type == "doi" and query:
            # Search by DOI
            api_url = f"{base_url}/DOI:{query}"
        elif query_type == "url" and query:
            # Search by URL
            api_url = f"{base_url}/URL:{query}"
        elif query_type == "pii" and query:
            # Search by title/query string
            api_url = f"{base_url}/search"
            params = {
                'query': query,
                'limit': 1,
                'fields': 'title,authors,year,publicationVenue,externalIds'
            }
        else:
            # General search
            api_url = f"{base_url}/search"
            params = {
                'query': query,
                'limit': 1,
                'fields': 'title,authors,year,publicationVenue,externalIds'
            }

        # Make request
        if query_type in ["doi", "url"]:
            params = {'fields': 'title,authors,year,publicationVenue,externalIds'}
            response = requests.get(api_url, params=params, timeout=10)
        else:
            response = requests.get(api_url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Handle search results vs direct lookup
            if 'data' in data and len(data['data']) > 0:
                paper = data['data'][0]
            elif 'title' in data:
                paper = data
            else:
                return None

            # Extract metadata
            result = {
                'title': paper.get('title'),
                'authors': [a.get('name', '') for a in paper.get('authors', [])],
                'year': str(paper.get('year', '')) if paper.get('year') else '',
                'journal': paper.get('publicationVenue', {}).get('name', ''),
                'doi': paper.get('externalIds', {}).get('DOI', '')
            }

            # Only return if we have a title
            if result['title']:
                return result

        return None

    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.RequestException:
        return None
    except Exception:
        return None


def main():
    print("=" * 80, flush=True)
    print("Fixing Unknown Titles Using Semantic Scholar", flush=True)
    print("=" * 80, flush=True)
    print(flush=True)

    # Load metadata
    metadata_file = Path("data/metadata.json")
    if not metadata_file.exists():
        print("[ERROR] metadata.json not found")
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
        print("[OK] No papers need fixing!")
        return

    # Process each paper
    fixed_count = 0
    still_unknown_count = 0

    for idx, (filename, paper) in enumerate(unknown_papers, 1):
        print(f"[{idx}/{len(unknown_papers)}] {filename}", flush=True)

        url = paper.get('url') or paper.get('source_url', '')
        doi = paper.get('doi', '')

        result = None

        # Strategy 1: Try PII from ScienceDirect URL
        if url and 'sciencedirect.com' in url.lower():
            pii = extract_pii_from_url(url)
            if pii:
                print(f"  [Strategy 1] Searching by PII: {pii}", flush=True)
                result = search_semantic_scholar(pii, query_type="pii")
                time.sleep(0.5)  # Rate limit

        # Strategy 2: Try DOI if present
        if not result and doi:
            print(f"  [Strategy 2] Searching by DOI: {doi}", flush=True)
            result = search_semantic_scholar(doi, query_type="doi")
            time.sleep(0.5)

        # Strategy 3: Try URL directly
        if not result and url:
            print(f"  [Strategy 3] Searching by URL: {url[:60]}...", flush=True)
            result = search_semantic_scholar(url, query_type="url")
            time.sleep(0.5)

        # Update if found
        if result and result.get('title'):
            paper['title'] = result['title']

            # Update other fields if we got them
            if result.get('authors'):
                paper['authors'] = result['authors']
            if result.get('year'):
                paper['year'] = result['year']
            if result.get('journal'):
                paper['journal'] = result['journal']
            if result.get('doi') and not paper.get('doi'):
                paper['doi'] = result['doi']

            fixed_count += 1
            print(f"  [+] FOUND: {result['title'][:70]}...", flush=True)
        else:
            still_unknown_count += 1
            print(f"  [-] Not found", flush=True)

        print(flush=True)

        # Save checkpoint every 50 papers
        if idx % 50 == 0:
            print(f"  [+] Checkpoint save at {idx}/{len(unknown_papers)}", flush=True)
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(all_metadata, f, indent=2, ensure_ascii=False)

    # Final save
    print("=" * 80)
    print("Saving changes...")
    print()

    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, indent=2, ensure_ascii=False)

    print("[+] Saved metadata.json")

    # Update ChromaDB
    print("[+] Updating ChromaDB...", flush=True)

    # Import DatabaseClient only when needed (avoid slow startup)
    from lib.rag import DatabaseClient

    update_count = 0
    error_count = 0

    for filename, paper, in unknown_papers:
        try:
            if paper['title'] != "Unknown - needs manual review":
                success = DatabaseClient.update_paper_metadata(filename, all_metadata[filename])
                if success:
                    update_count += 1
                else:
                    error_count += 1
        except Exception as e:
            error_count += 1
            print(f"  [WARN] ChromaDB update failed for {filename}: {e}")

    print(f"[+] Updated {update_count} papers in ChromaDB")
    if error_count > 0:
        print(f"[WARN] {error_count} ChromaDB updates failed")

    # Clear caches
    DatabaseClient.clear_cache()
    print("[+] Cleared caches")

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Papers to process:            {len(unknown_papers)}")
    print(f"Successfully fixed:           {fixed_count} ({fixed_count/len(unknown_papers)*100:.1f}%)")
    print(f"Still unknown:                {still_unknown_count} ({still_unknown_count/len(unknown_papers)*100:.1f}%)")
    print()

    if still_unknown_count > 0:
        print("[NOTE] Papers still marked 'Unknown - needs manual review':")
        count = 0
        for filename, paper in unknown_papers:
            if paper['title'] == "Unknown - needs manual review":
                print(f"  - {filename}: {paper.get('url', 'N/A')[:60]}")
                count += 1
                if count >= 10:
                    print(f"  ... and {still_unknown_count - 10} more")
                    break
        print()

    print("[OK] Done! Restart the Streamlit app to see changes.")


if __name__ == "__main__":
    main()
