"""
Test what happens when we try to import the same paper twice
"""
import json
import re
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

def is_paper_in_library(title: str, doi: str, existing_papers: list) -> bool:
    """Check if paper is already in library (same as app.py)"""
    if not title:
        return False

    norm_title = normalize_title_for_matching(title)

    for paper in existing_papers:
        # Check by DOI if both have DOI
        if doi and paper.get('doi'):
            if doi.lower() == paper.get('doi', '').lower():
                return True

        # Check by title similarity
        paper_title = normalize_title_for_matching(paper.get('title', ''))
        if paper_title and norm_title:
            # Use simple similarity: check if 90% of words match
            title_words = set(norm_title.split())
            paper_words = set(paper_title.split())

            if title_words and paper_words:
                overlap = len(title_words & paper_words)
                similarity = overlap / max(len(title_words), len(paper_words))

                if similarity > 0.9:
                    return True

    return False

# Load library
metadata_file = Path("data/metadata.json")
with open(metadata_file, 'r', encoding='utf-8') as f:
    library = json.load(f)

existing_papers = list(library.values())

print("="*80)
print("TEST: Re-importing existing papers")
print("="*80)

# Test papers that ARE in the library
test_cases = [
    {
        'title': 'Data-driven Prediction of Battery Cycle Life Before Capacity Degradation',
        'doi': '10.1038/s41560-019-0356-8',  # Clean DOI format
        'description': 'Paper #1 - Clean DOI'
    },
    {
        'title': 'Dynamic cycling enhances battery lifetime',
        'doi': '10.1038/s41560-024-01675-8',  # Clean DOI format
        'description': 'Paper #2 - Clean DOI'
    },
    {
        'title': 'History-agnostic battery degradation inference',
        'doi': 'https://doi.org/10.1016/j.est.2023.110279',  # URL format DOI
        'description': 'Paper #3 - URL format DOI'
    },
    {
        'title': 'Data-driven Prediction of Battery Cycle Life Before Capacity Degradation',
        'doi': 'https://doi.org/10.1038/s41560-019-0356-8',  # URL format DOI but clean in library
        'description': 'Paper #4 - DOI format mismatch (URL vs clean)'
    }
]

for i, test in enumerate(test_cases, 1):
    print(f"\n{i}. {test['description']}")
    print(f"   Title: {test['title']}")
    print(f"   DOI: {test['doi']}")

    is_duplicate = is_paper_in_library(test['title'], test['doi'], existing_papers)

    if is_duplicate:
        print(f"   Result: [DUPLICATE DETECTED] - Would be skipped")
    else:
        print(f"   Result: [NOT DETECTED] - Would be imported (DUPLICATE!)")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print("If any papers show 'NOT DETECTED' but are actually in the library,")
print("then duplicate detection is broken.")
