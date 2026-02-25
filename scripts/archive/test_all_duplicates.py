"""
Test ALL papers from CSV to find which ones should be duplicates but aren't detected
"""
import json
import csv
import re
from pathlib import Path
from lib import rag

def normalize_title_for_matching(title: str) -> str:
    if not title:
        return ""
    normalized = title.lower()
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

def is_paper_in_library(title: str, doi: str, existing_papers: list) -> bool:
    if not title:
        return False

    norm_title = normalize_title_for_matching(title)

    for paper in existing_papers:
        if doi and paper.get('doi'):
            if doi.lower() == paper.get('doi', '').lower():
                return True

        paper_title = normalize_title_for_matching(paper.get('title', ''))
        if paper_title and norm_title:
            title_words = set(norm_title.split())
            paper_words = set(paper_title.split())

            if title_words and paper_words:
                overlap = len(title_words & paper_words)
                similarity = overlap / max(len(title_words), len(paper_words))

                if similarity > 0.9:
                    return True

    return False

# Load papers
from lib.rag import DatabaseClient
DatabaseClient.clear_cache()
papers = rag.get_paper_library()
print(f"Library has {len(papers)} papers")
print()

# Build a set of normalized library titles for quick matching
library_titles = {}
for paper in papers:
    norm_title = normalize_title_for_matching(paper.get('title', ''))
    library_titles[norm_title] = paper.get('title', '')

# Load CSV
csv_file = Path(r"C:\Users\rcmas\Downloads\notion_papers_all.csv")
with open(csv_file, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)

    print("Checking ALL CSV papers for false negatives...")
    print("(Papers that ARE in library but NOT detected as duplicates)")
    print("="*80)

    bugs_found = 0
    checked = 0

    for row in reader:
        title = row.get('Title', '').strip()
        url = row.get('URL', '').strip()

        if not title:
            continue

        # Check if this CSV title matches any library title at >95% similarity
        norm_csv = normalize_title_for_matching(title)
        csv_words = set(norm_csv.split())

        best_match = None
        best_similarity = 0

        for norm_lib, lib_title in library_titles.items():
            lib_words = set(norm_lib.split())

            if csv_words and lib_words:
                overlap = len(csv_words & lib_words)
                similarity = overlap / max(len(csv_words), len(lib_words))

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = lib_title

        # If we have a very high similarity match (>95%), this should be detected as duplicate
        if best_similarity > 0.95:
            # Test if duplicate detection would catch it
            doi = url.split('doi.org/')[-1] if 'doi.org/' in url else ''
            detected = is_paper_in_library(title, doi, papers)

            if not detected:
                bugs_found += 1
                print(f"\n[BUG #{bugs_found}] Paper in library but NOT detected:")
                print(f"  CSV title:     {title[:70]}...")
                print(f"  Library title: {best_match[:70]}...")
                print(f"  Similarity: {best_similarity:.2%}")
                print(f"  CSV normalized:     {norm_csv[:70]}...")
                print(f"  Library normalized: {normalize_title_for_matching(best_match)[:70]}...")

        checked += 1
        if checked % 100 == 0:
            print(f"Checked {checked} papers... ({bugs_found} bugs found so far)")

print()
print("="*80)
print(f"Total papers checked: {checked}")
print(f"Bugs found: {bugs_found}")
print("="*80)

if bugs_found == 0:
    print("\nNo bugs found! Duplicate detection working correctly.")
else:
    print(f"\nFound {bugs_found} papers that should be detected as duplicates but aren't.")
