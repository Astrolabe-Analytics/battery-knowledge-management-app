"""
Test duplicate detection during CSV import
Simulate the exact flow the app uses
"""
import json
import csv
import re
from pathlib import Path
from lib import rag

def normalize_title_for_matching(title: str) -> str:
    """Same as app.py"""
    if not title:
        return ""
    normalized = title.lower()
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

def is_paper_in_library(title: str, doi: str, existing_papers: list) -> bool:
    """Same as app.py"""
    if not title:
        return False

    norm_title = normalize_title_for_matching(title)

    for paper in existing_papers:
        # Check by DOI if both have DOI
        if doi and paper.get('doi'):
            if doi.lower() == paper.get('doi', '').lower():
                print(f"      [DOI MATCH] {doi}")
                return True

        # Check by title similarity
        paper_title = normalize_title_for_matching(paper.get('title', ''))
        if paper_title and norm_title:
            title_words = set(norm_title.split())
            paper_words = set(paper_title.split())

            if title_words and paper_words:
                overlap = len(title_words & paper_words)
                similarity = overlap / max(len(title_words), len(paper_words))

                if similarity > 0.9:
                    print(f"      [TITLE MATCH] {similarity:.2%}")
                    print(f"        CSV:     {norm_title[:70]}...")
                    print(f"        Library: {paper_title[:70]}...")
                    return True

    return False

# Clear cache first
from lib.rag import DatabaseClient
DatabaseClient.clear_cache()

# Load papers exactly like the app does at line 1263
print("Loading papers from library...")
papers = rag.get_paper_library()
print(f"Loaded {len(papers)} papers")
print()

# Check that key papers are in the list
print("Checking if known papers are in library:")
print("="*80)

known_papers = [
    "Dynamic cycling enhances battery lifetime",
    "The generalisation challenge",
    "Data-driven prediction"
]

for search_term in known_papers:
    found = False
    for paper in papers:
        if search_term.lower() in paper.get('title', '').lower():
            print(f"[FOUND] {paper.get('title', '')[:60]}...")
            found = True
            break
    if not found:
        print(f"[NOT FOUND] {search_term}")

print()
print("="*80)
print("Testing CSV import duplicate detection:")
print("="*80)

# Load CSV
csv_file = Path(r"C:\Users\rcmas\Downloads\notion_papers_all.csv")
if not csv_file.exists():
    print(f"ERROR: CSV not found at {csv_file}")
    exit(1)

with open(csv_file, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)

    tested = 0
    skipped = 0
    imported = 0

    for row in reader:
        title = row.get('Title', '').strip()
        url = row.get('URL', '').strip()

        # Only test papers we care about
        if any(term.lower() in title.lower() for term in known_papers):
            doi = url.split('doi.org/')[-1] if 'doi.org/' in url else ''

            print(f"\n{tested + 1}. Testing: {title[:70]}...")
            print(f"   URL: {url[:80]}...")
            print(f"   DOI: {doi if doi else '(none)'}")

            is_duplicate = is_paper_in_library(title, doi, papers)

            if is_duplicate:
                print(f"   Result: [SKIP] - Duplicate detected")
                skipped += 1
            else:
                print(f"   Result: [IMPORT] - NOT detected as duplicate (BUG!)")
                imported += 1

            tested += 1

            if tested >= 5:  # Test first 5 matches
                break

print()
print("="*80)
print(f"Summary: {skipped} duplicates skipped, {imported} would be re-imported")
print("="*80)

if imported > 0:
    print("\nBUG CONFIRMED: Some papers are not being detected as duplicates")
else:
    print("\nDuplicate detection working correctly!")
