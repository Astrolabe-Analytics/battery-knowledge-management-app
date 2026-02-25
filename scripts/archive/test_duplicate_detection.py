"""
Test duplicate detection to understand why it's not working
"""
import json
import re
import csv
from pathlib import Path

def normalize_title_for_matching(title: str) -> str:
    """Normalize title for duplicate detection (same as in app.py)"""
    if not title:
        return ""
    # Lowercase, remove punctuation, collapse whitespace
    normalized = title.lower()
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

def check_title_similarity(title1: str, title2: str) -> float:
    """Check similarity between two titles"""
    norm1 = normalize_title_for_matching(title1)
    norm2 = normalize_title_for_matching(title2)

    if not norm1 or not norm2:
        return 0.0

    words1 = set(norm1.split())
    words2 = set(norm2.split())

    if not words1 or not words2:
        return 0.0

    overlap = len(words1 & words2)
    similarity = overlap / max(len(words1), len(words2))

    return similarity

# Load library metadata
print("=" * 100)
print("DUPLICATE DETECTION ANALYSIS")
print("=" * 100)

metadata_file = Path("data/metadata.json")
with open(metadata_file, 'r', encoding='utf-8') as f:
    library = json.load(f)

print(f"\nLibrary has {len(library)} papers")

# Find the CSV file
csv_file = Path(r"C:\Users\rcmas\Downloads\notion_papers_all.csv")
if not csv_file.exists():
    print(f"\nERROR: CSV not found at {csv_file}")
    print("Please update the path in the script")
    exit(1)

# Load CSV (handle BOM)
print(f"Loading CSV: {csv_file}")
csv_papers = []
with open(csv_file, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        title = row.get('Title', '').strip()
        url = row.get('URL', '').strip()
        if title:
            csv_papers.append({
                'title': title,
                'url': url
            })

print(f"CSV has {len(csv_papers)} papers with titles")

# Test Case 1: "Dynamic cycling enhances battery lifetime" (the one that works)
print("\n" + "=" * 100)
print("TEST CASE 1: Paper that IS correctly detected as duplicate")
print("=" * 100)

csv_target = "Dynamic cycling enhances battery lifetime"
print(f"\nSearching for: {csv_target}")

# Find in CSV
csv_match = None
for p in csv_papers:
    if csv_target.lower() in p['title'].lower():
        csv_match = p
        break

if csv_match:
    print(f"\nFound in CSV:")
    print(f"  Title: {csv_match['title']}")
    print(f"  URL: {csv_match['url']}")
    print(f"  Normalized: {normalize_title_for_matching(csv_match['title'])}")

    # Find matches in library
    print(f"\nSearching library for matches...")
    best_match = None
    best_similarity = 0

    for filename, paper in library.items():
        lib_title = paper.get('title', '')
        similarity = check_title_similarity(csv_match['title'], lib_title)

        if similarity > best_similarity:
            best_similarity = similarity
            best_match = (filename, paper, similarity)

        if similarity > 0.9:
            print(f"\n  MATCH (similarity: {similarity:.2%}):")
            print(f"    Library title: {lib_title}")
            print(f"    Library DOI: {paper.get('doi', 'NONE')}")
            print(f"    Library normalized: {normalize_title_for_matching(lib_title)}")
            print(f"    Filename: {filename}")
            break

    if best_similarity < 0.9:
        print(f"\n  No match found (best similarity: {best_similarity:.2%})")
        if best_match:
            print(f"    Best match was: {best_match[1].get('title', '')[:60]}...")

# Test Case 2: Papers that are NOT being detected (take first 3 from CSV)
print("\n" + "=" * 100)
print("TEST CASE 2: Papers that are NOT being detected as duplicates")
print("=" * 100)

print("\nTesting first 10 papers from CSV...")

for i, csv_paper in enumerate(csv_papers[:10], 1):
    csv_title = csv_paper['title']
    csv_url = csv_paper['url']

    print(f"\n{i}. CSV Title: {csv_title[:70]}...")
    print(f"   URL: {csv_url[:80]}..." if csv_url else "   URL: NONE")
    print(f"   Normalized: {normalize_title_for_matching(csv_title)[:70]}...")

    # Search library for match
    found_match = False
    for filename, paper in library.items():
        lib_title = paper.get('title', '')
        lib_doi = paper.get('doi', '')

        similarity = check_title_similarity(csv_title, lib_title)

        if similarity > 0.9:
            print(f"   [DUPLICATE DETECTED] (similarity: {similarity:.2%})")
            print(f"     Library title: {lib_title[:70]}...")
            print(f"     Library DOI: {lib_doi}")
            print(f"     Match reason: {'DOI match' if lib_doi and csv_url and lib_doi in csv_url else 'Title match'}")
            found_match = True
            break

    if not found_match:
        print(f"   [NOT DETECTED] - Would be re-added!")
        # Find closest match to see why it didn't match
        best_match = None
        best_similarity = 0

        for filename, paper in library.items():
            lib_title = paper.get('title', '')
            similarity = check_title_similarity(csv_title, lib_title)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = (lib_title, similarity)

        if best_match and best_match[1] > 0.5:
            print(f"     Closest match: {best_match[0][:70]}... (similarity: {best_match[1]:.2%})")
            print(f"     Why it didn't match: Similarity {best_match[1]:.2%} < 90% threshold")

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print("\nTo fix duplicate detection, we need to understand:")
print("1. Are titles in library truncated?")
print("2. Are DOIs being extracted and matched correctly?")
print("3. Is the 90% threshold too high?")
print("=" * 100)
