"""
Fix papers where title field contains a URL instead of actual title.

This script:
1. Finds papers with URLs as titles
2. Moves URL to url field
3. Extracts DOI and looks up real title from CrossRef
4. Falls back to Semantic Scholar search if no DOI
5. Updates metadata.json and ChromaDB
"""

import json
import re
import time
from pathlib import Path
import sys
import io

# Fix console encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.app_helpers import (
    extract_doi_from_url,
    query_crossref_for_metadata,
    find_doi_via_semantic_scholar
)
from lib.rag import DatabaseClient


def is_url(text: str) -> bool:
    """Check if text looks like a URL."""
    if not text:
        return False

    text = text.strip().lower()

    # Check for common URL patterns
    url_patterns = [
        r'^https?://',
        r'www\.',
        r'\.(com|org|io|edu|gov|net|co\.uk|de|fr|jp|cn|au)',
    ]

    for pattern in url_patterns:
        if re.search(pattern, text):
            return True

    return False


def search_semantic_scholar_by_url(url: str) -> dict:
    """Search Semantic Scholar by URL to get paper metadata."""
    try:
        import requests

        # Try searching by URL
        api_url = f"https://api.semanticscholar.org/graph/v1/paper/URL:{url}"
        params = {
            'fields': 'title,authors,year,publicationVenue,externalIds'
        }

        response = requests.get(api_url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return {
                'title': data.get('title'),
                'authors': [a['name'] for a in data.get('authors', [])],
                'year': str(data.get('year', '')),
                'journal': data.get('publicationVenue', {}).get('name', ''),
                'doi': data.get('externalIds', {}).get('DOI', '')
            }
    except Exception as e:
        print(f"  [Semantic Scholar] Error: {e}")

    return None


def main():
    print("=" * 80)
    print("Fixing URL-as-Title Issues")
    print("=" * 80)
    print()

    # Load metadata
    metadata_file = Path("data/metadata.json")
    if not metadata_file.exists():
        print("[ERROR] Error: metadata.json not found")
        return

    with open(metadata_file, 'r', encoding='utf-8') as f:
        all_metadata = json.load(f)

    print(f"Loaded {len(all_metadata)} papers from metadata.json")
    print()

    # Step 1: Find papers with URL as title
    url_title_papers = []
    for filename, paper in all_metadata.items():
        title = paper.get('title', '')
        if is_url(title):
            url_title_papers.append((filename, paper, title))

    print(f"Found {len(url_title_papers)} papers with URL as title")
    print()

    if len(url_title_papers) == 0:
        print("[OK] No papers need fixing!")
        return

    # Process each paper
    fixed_count = 0
    needs_review_count = 0
    failed_count = 0

    for idx, (filename, paper, url_title) in enumerate(url_title_papers, 1):
        print(f"[{idx}/{len(url_title_papers)}] Processing: {filename}")
        print(f"  Current title (URL): {url_title[:80]}...")

        # Step 2: Move URL to url field if not set
        if not paper.get('url') and not paper.get('source_url'):
            paper['url'] = url_title
            paper['source_url'] = url_title
            print(f"  [+] Moved URL to url field")

        url = paper.get('url') or paper.get('source_url') or url_title

        # Step 3: Try to find real title
        real_title = None

        # Method 1: Extract DOI from URL and query CrossRef
        print(f"  [Method 1] Trying DOI extraction from URL...")
        doi = extract_doi_from_url(url)

        if doi:
            print(f"  [+] Found DOI: {doi}")
            crossref_data = query_crossref_for_metadata(doi)

            if crossref_data and crossref_data.get('title'):
                real_title = crossref_data['title']
                print(f"  [+] Found title from CrossRef: {real_title[:60]}...")

                # Update other metadata too if available
                if crossref_data.get('authors'):
                    paper['authors'] = crossref_data['authors']
                if crossref_data.get('year'):
                    paper['year'] = crossref_data['year']
                if crossref_data.get('journal'):
                    paper['journal'] = crossref_data['journal']

                paper['doi'] = doi

                fixed_count += 1
            else:
                print(f"  [WARN] DOI found but CrossRef lookup failed")

        # Method 2: Search Semantic Scholar by URL
        if not real_title:
            print(f"  [Method 2] Trying Semantic Scholar search by URL...")
            time.sleep(1)  # Rate limit

            ss_data = search_semantic_scholar_by_url(url)

            if ss_data and ss_data.get('title'):
                real_title = ss_data['title']
                print(f"  [+] Found title from Semantic Scholar: {real_title[:60]}...")

                # Update other metadata too
                if ss_data.get('authors'):
                    paper['authors'] = ss_data['authors']
                if ss_data.get('year'):
                    paper['year'] = ss_data['year']
                if ss_data.get('journal'):
                    paper['journal'] = ss_data['journal']
                if ss_data.get('doi'):
                    paper['doi'] = ss_data['doi']

                fixed_count += 1
            else:
                print(f"  [WARN] Semantic Scholar lookup failed")

        # Step 4: Update title
        if real_title:
            paper['title'] = real_title
        else:
            paper['title'] = "Unknown - needs manual review"
            needs_review_count += 1
            print(f"  [ERROR] Could not find real title - marked for manual review")

        print()

        # Rate limiting
        time.sleep(0.5)

    # Step 5: Save updated metadata
    print("=" * 80)
    print("Saving changes...")
    print()

    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, indent=2, ensure_ascii=False)

    print("[+] Saved metadata.json")

    # Update ChromaDB
    print("[+] Updating ChromaDB...")
    for filename, paper, _ in url_title_papers:
        try:
            DatabaseClient.update_paper_metadata(filename, all_metadata[filename])
        except Exception as e:
            print(f"  [WARN] ChromaDB update failed for {filename}: {e}")

    # Clear caches
    DatabaseClient.clear_cache()
    print("[+] Cleared caches")

    # Step 6: Print summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Papers with URL as title:     {len(url_title_papers)}")
    print(f"Successfully fixed:           {fixed_count}")
    print(f"Needs manual review:          {needs_review_count}")
    print(f"Failed:                       {failed_count}")
    print()

    if needs_review_count > 0:
        print("[NOTE] Papers marked 'Unknown - needs manual review':")
        for filename, paper, _ in url_title_papers:
            if paper['title'] == "Unknown - needs manual review":
                print(f"  - {filename}")
                print(f"    URL: {paper.get('url', 'N/A')}")
        print()

    print("[OK] Done! Restart the Streamlit app to see changes.")


if __name__ == "__main__":
    main()
