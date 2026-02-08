"""
Fix papers with URL-as-title by fetching the HTML page title.

Simple approach: Just fetch each URL and extract the <title> tag.
Much faster and more reliable than DOI/API lookups.
"""

import json
import re
import time
from pathlib import Path
import sys
import io
import requests
from bs4 import BeautifulSoup

# Fix console encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

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


def clean_title(title: str) -> str:
    """Clean up HTML title by removing publisher suffixes."""
    if not title:
        return None

    # Common suffixes to remove
    suffixes = [
        r'\s*-\s*ScienceDirect',
        r'\s*\|\s*ScienceDirect',
        r'\s*-\s*Nature',
        r'\s*\|\s*Nature',
        r'\s*-\s*SpringerLink',
        r'\s*\|\s*SpringerLink',
        r'\s*-\s*Wiley Online Library',
        r'\s*\|\s*Wiley Online Library',
        r'\s*-\s*IEEE Xplore',
        r'\s*\|\s*IEEE Xplore',
        r'\s*-\s*MDPI',
        r'\s*\|\s*MDPI',
        r'\s*-\s*Elsevier',
        r'\s*\|\s*Elsevier',
        r'\s*-\s*Journal.*',  # Remove " - Journal of XYZ" suffixes
        r'\s*\|\s*.*Journal.*',
        r'\s*[\|\-]\s*\d{4}$',  # Remove year at end
    ]

    cleaned = title.strip()

    for suffix in suffixes:
        cleaned = re.sub(suffix, '', cleaned, flags=re.IGNORECASE)

    cleaned = cleaned.strip()

    # If title is too short or looks invalid, return None
    if len(cleaned) < 10:
        return None

    return cleaned


def fetch_title_from_url(url: str) -> str:
    """Fetch URL and extract title from HTML."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title_tag = soup.find('title')

            if title_tag and title_tag.string:
                raw_title = title_tag.string.strip()
                cleaned = clean_title(raw_title)

                if cleaned:
                    return cleaned

    except requests.exceptions.Timeout:
        print("    [WARN] Timeout")
    except requests.exceptions.RequestException as e:
        print(f"    [WARN] Request failed: {type(e).__name__}")
    except Exception as e:
        print(f"    [WARN] Error: {type(e).__name__}")

    return None


def main():
    print("=" * 80)
    print("Fixing URL-as-Title Issues (Simple HTML Fetch Method)")
    print("=" * 80)
    print()

    # Load metadata
    metadata_file = Path("data/metadata.json")
    if not metadata_file.exists():
        print("[ERROR] metadata.json not found")
        return

    with open(metadata_file, 'r', encoding='utf-8') as f:
        all_metadata = json.load(f)

    print(f"Loaded {len(all_metadata)} papers from metadata.json")
    print()

    # Find papers with URL as title
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

    for idx, (filename, paper, url_title) in enumerate(url_title_papers, 1):
        print(f"[{idx}/{len(url_title_papers)}] {filename}")

        # Move URL to url field if not set
        if not paper.get('url') and not paper.get('source_url'):
            paper['url'] = url_title
            paper['source_url'] = url_title

        url = paper.get('url') or paper.get('source_url') or url_title

        # Fetch title from URL
        print(f"  Fetching: {url[:70]}...")
        real_title = fetch_title_from_url(url)

        if real_title:
            paper['title'] = real_title
            fixed_count += 1
            print(f"  [+] Title: {real_title[:70]}...")
        else:
            paper['title'] = "Unknown - needs manual review"
            needs_review_count += 1
            print(f"  [ERROR] Could not extract title")

        print()

        # Rate limit: 1 request per second
        time.sleep(1)

        # Save every 50 papers to avoid data loss
        if idx % 50 == 0:
            print(f"  [+] Checkpoint save at {idx}/{len(url_title_papers)}")
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
    print("[+] Updating ChromaDB...")
    for filename, paper, _ in url_title_papers:
        try:
            DatabaseClient.update_paper_metadata(filename, all_metadata[filename])
        except Exception as e:
            print(f"  [WARN] ChromaDB update failed for {filename}: {e}")

    # Clear caches
    DatabaseClient.clear_cache()
    print("[+] Cleared caches")

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Papers with URL as title:     {len(url_title_papers)}")
    print(f"Successfully fixed:           {fixed_count}")
    print(f"Needs manual review:          {needs_review_count}")
    print()

    if needs_review_count > 0:
        print("[NOTE] Papers marked 'Unknown - needs manual review':")
        count = 0
        for filename, paper, _ in url_title_papers:
            if paper['title'] == "Unknown - needs manual review":
                print(f"  - {filename}: {paper.get('url', 'N/A')[:60]}")
                count += 1
                if count >= 10:
                    print(f"  ... and {needs_review_count - 10} more")
                    break
        print()

    print("[OK] Done! Restart the Streamlit app to see changes.")


if __name__ == "__main__":
    main()
