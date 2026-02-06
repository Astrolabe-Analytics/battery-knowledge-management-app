"""
Gap Analysis - Find frequently cited papers missing from library.

Analyzes all references across papers in the library to identify the most
frequently cited papers that are not yet in the library.
"""

import json
from pathlib import Path
from typing import List, Dict, Set
from collections import defaultdict
from difflib import SequenceMatcher


def normalize_doi(doi_string: str) -> str:
    """
    Normalize DOI by removing URL prefix and converting to lowercase.

    Args:
        doi_string: DOI string (may include URL prefix)

    Returns:
        Normalized DOI string
    """
    if not doi_string:
        return ''

    doi = doi_string.lower().strip()

    # Remove common DOI URL prefixes
    for prefix in ['https://doi.org/', 'http://doi.org/', 'doi.org/', 'doi:']:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]

    return doi


def normalize_title(title: str) -> str:
    """
    Normalize title for matching (lowercase, remove extra whitespace).

    Args:
        title: Paper title

    Returns:
        Normalized title
    """
    if not title:
        return ''

    # Lowercase and remove extra whitespace
    title = ' '.join(title.lower().strip().split())
    return title


def titles_match(title1: str, title2: str, threshold: float = 0.9) -> bool:
    """
    Check if two titles match using fuzzy matching.

    Args:
        title1: First title
        title2: Second title
        threshold: Similarity threshold (0-1)

    Returns:
        True if titles match above threshold
    """
    if not title1 or not title2:
        return False

    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)

    # Exact match
    if norm1 == norm2:
        return True

    # Fuzzy match
    ratio = SequenceMatcher(None, norm1, norm2).ratio()
    return ratio >= threshold


def analyze_reference_gaps(metadata_file: Path = None) -> List[Dict]:
    """
    Analyze all references to find frequently cited papers missing from library.

    Args:
        metadata_file: Path to metadata.json (default: data/metadata.json)

    Returns:
        List of dicts with reference info sorted by citation count:
        {
            'title': str,
            'authors': str,
            'year': str,
            'journal': str,
            'doi': str,
            'citation_count': int,
            'cited_by': List[str]  # List of paper titles that cite this
        }
    """
    if metadata_file is None:
        metadata_file = Path(__file__).parent.parent / "data" / "metadata.json"

    if not metadata_file.exists():
        return []

    # Load metadata
    with open(metadata_file, 'r', encoding='utf-8') as f:
        all_metadata = json.load(f)

    # Build library lookup: DOIs and titles
    library_dois = set()
    library_titles = set()

    for filename, paper in all_metadata.items():
        # Collect library DOIs
        if paper.get('doi'):
            library_dois.add(normalize_doi(paper['doi']))

        # Collect library titles (normalized)
        if paper.get('title'):
            library_titles.add(normalize_title(paper['title']))

    # Aggregate references across all papers
    # Key: normalized DOI or title
    # Value: reference data + citation info
    reference_aggregator = defaultdict(lambda: {
        'title': '',
        'authors': '',
        'year': '',
        'journal': '',
        'doi': '',
        'citation_count': 0,
        'cited_by': []
    })

    # Process each paper's references
    for filename, paper in all_metadata.items():
        paper_title = paper.get('title', filename.replace('.pdf', ''))
        references = paper.get('references', [])

        for ref in references:
            # Skip incomplete references
            title = ref.get('article-title', '').strip()
            authors = ref.get('author', '').strip()

            if not title or not authors:
                continue  # Skip incomplete references

            # Determine lookup key (prefer DOI, fall back to title)
            ref_doi = normalize_doi(ref.get('DOI', ''))
            lookup_key = ref_doi if ref_doi else normalize_title(title)

            if not lookup_key:
                continue

            # Check if this reference is already in library
            in_library = False

            if ref_doi and ref_doi in library_dois:
                in_library = True
            elif not ref_doi:
                # Check by title match
                norm_title = normalize_title(title)
                if norm_title in library_titles:
                    in_library = True
                else:
                    # Fuzzy title matching (slower but more accurate)
                    for lib_title in library_titles:
                        if titles_match(norm_title, lib_title, threshold=0.9):
                            in_library = True
                            break

            # Skip if already in library
            if in_library:
                continue

            # Aggregate this reference
            agg = reference_aggregator[lookup_key]

            # Update reference data (prefer first occurrence with most complete data)
            if not agg['title'] or len(title) > len(agg['title']):
                agg['title'] = title

            if not agg['authors'] or len(authors) > len(agg['authors']):
                agg['authors'] = authors

            year = ref.get('year', '')
            if year and (not agg['year'] or year > agg['year']):
                agg['year'] = str(year) if year else ''

            journal = ref.get('journal-title', '')
            if journal and (not agg['journal'] or len(journal) > len(agg['journal'])):
                agg['journal'] = journal

            if ref_doi and not agg['doi']:
                agg['doi'] = ref.get('DOI', '')  # Use original (non-normalized) DOI

            # Increment citation count
            agg['citation_count'] += 1

            # Track which papers cite this reference
            if paper_title not in agg['cited_by']:
                agg['cited_by'].append(paper_title)

    # Convert aggregator to sorted list
    gaps = []
    for key, data in reference_aggregator.items():
        if data['citation_count'] > 0:  # Only include referenced papers
            gaps.append(data)

    # Sort by citation count (descending)
    gaps.sort(key=lambda x: x['citation_count'], reverse=True)

    return gaps


def get_top_gaps(n: int = 20, metadata_file: Path = None) -> List[Dict]:
    """
    Get top N most frequently cited papers missing from library.

    Args:
        n: Number of top gaps to return (default: 20)
        metadata_file: Path to metadata.json

    Returns:
        List of top N gap references
    """
    all_gaps = analyze_reference_gaps(metadata_file)
    return all_gaps[:n]


def get_gap_statistics(metadata_file: Path = None) -> Dict:
    """
    Get statistics about reference gaps.

    Args:
        metadata_file: Path to metadata.json

    Returns:
        Dict with statistics:
        {
            'total_gaps': int,
            'total_citations': int,
            'avg_citations_per_gap': float,
            'top_gap_count': int (citations of most cited gap)
        }
    """
    gaps = analyze_reference_gaps(metadata_file)

    if not gaps:
        return {
            'total_gaps': 0,
            'total_citations': 0,
            'avg_citations_per_gap': 0.0,
            'top_gap_count': 0
        }

    total_citations = sum(g['citation_count'] for g in gaps)

    return {
        'total_gaps': len(gaps),
        'total_citations': total_citations,
        'avg_citations_per_gap': round(total_citations / len(gaps), 2),
        'top_gap_count': gaps[0]['citation_count'] if gaps else 0
    }
