"""
Backfill URLs from Notion CSV to existing papers in metadata.json

Usage: python backfill_urls.py [path_to_notion_csv]
"""
import json
import csv
import re
import sys
from pathlib import Path
from difflib import SequenceMatcher

def normalize_title(title: str) -> str:
    """Normalize title for matching"""
    if not title:
        return ""
    # Lowercase, remove extra whitespace, remove punctuation
    title = title.lower()
    title = re.sub(r'[^\w\s]', ' ', title)
    title = ' '.join(title.split())
    return title

def titles_match(title1: str, title2: str, threshold: float = 0.90) -> bool:
    """Check if two titles match with fuzzy matching"""
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)

    if not norm1 or not norm2:
        return False

    # Exact match
    if norm1 == norm2:
        return True

    # Fuzzy match
    ratio = SequenceMatcher(None, norm1, norm2).ratio()
    return ratio >= threshold

def main():
    # Paths
    metadata_file = Path("data/metadata.json")

    # Get CSV path from command line or use default
    if len(sys.argv) > 1:
        notion_csv = Path(sys.argv[1])
    else:
        # Try common locations
        possible_paths = [
            Path(r"C:\Users\rcmas\Downloads\Export-bccdef9a-8fd0-804a-b8e2-efb00c9e52ec_all.csv"),
            Path(r"C:\Users\rcmas\Downloads\export.csv"),
        ]
        notion_csv = None
        for p in possible_paths:
            if p.exists():
                notion_csv = p
                break

        if not notion_csv:
            print("ERROR: No Notion CSV found in default locations.")
            print(f"Usage: python backfill_urls.py [path_to_notion_csv]")
            print(f"\nTried:")
            for p in possible_paths:
                print(f"  - {p}")
            return

    # Load metadata
    print("Loading metadata.json...")
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Count papers without source_url
    papers_without_url = []
    for filename, paper in metadata.items():
        source_url = paper.get('source_url', '').strip()
        if not source_url:
            papers_without_url.append((filename, paper))

    print(f"\nFound {len(papers_without_url)} papers without source_url (out of {len(metadata)} total)")

    # Load Notion CSV
    print(f"\nLoading Notion CSV from: {notion_csv}")
    if not notion_csv.exists():
        print(f"ERROR: CSV file not found: {notion_csv}")
        return

    csv_data = []
    with open(notion_csv, 'r', encoding='utf-8-sig') as f:  # utf-8-sig handles BOM
        reader = csv.DictReader(f)
        row_count = 0
        for row in reader:
            row_count += 1
            title = row.get('Title', '').strip()
            url = row.get('URL', '').strip()

            # Debug first row
            if row_count == 1:
                print(f"First row keys: {list(row.keys())[:5]}")
                print(f"First row Title: '{title[:50] if title else 'EMPTY'}'")
                print(f"First row URL: '{url[:50] if url else 'EMPTY'}'")

            if title and url:
                csv_data.append({'title': title, 'url': url})

    print(f"Loaded {len(csv_data)} papers from CSV with titles and URLs (out of {row_count} rows)")

    # Match and update
    print("\nMatching papers by title and updating URLs...")
    matches = []
    updated_count = 0

    for filename, paper in papers_without_url[:100]:  # Limit to first 100 for testing
        paper_title = paper.get('title', '')

        # Try to find matching CSV entry
        for csv_entry in csv_data:
            if titles_match(paper_title, csv_entry['title']):
                matches.append({
                    'filename': filename,
                    'title': paper_title,
                    'url': csv_entry['url'],
                    'before': {k: v for k, v in paper.items() if k in ['title', 'authors', 'year', 'journal', 'source_url', 'doi']},
                })

                # Update metadata
                paper['source_url'] = csv_entry['url']
                updated_count += 1
                break

    print(f"Matched and updated {updated_count} papers")

    # Save updated metadata
    if updated_count > 0:
        print("\nSaving updated metadata.json...")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print("Saved")

    # Show first 5 matches BEFORE enrichment
    print("\nFirst 5 matched papers (BEFORE enrichment):")
    for i, match in enumerate(matches[:5], 1):
        print(f"\n{i}. {match['title'][:80]}")
        print(f"   URL: {match['url']}")
        print(f"   Authors: {match['before'].get('authors', 'N/A')}")
        print(f"   Year: {match['before'].get('year', 'N/A')}")
        print(f"   Journal: {match['before'].get('journal', 'N/A')}")
        print(f"   DOI: {match['before'].get('doi', 'N/A')}")

    print(f"\nBackfill complete! Updated {updated_count} papers with URLs.")
    print(f"Saved results to: backfill_results.json")

    # Save results for later comparison
    with open('backfill_results.json', 'w', encoding='utf-8') as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    main()
