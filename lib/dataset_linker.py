"""
Paper ↔ Dataset cross-referencing.

Links papers in the Astrolabe paper library to datasets in the battery
datasets catalog by matching on DOIs, URLs, and title similarity.

The catalog CSV lives in the data-visualization-tool repo:
  battery_datasets_catalog_jan17_2026.csv

This module provides:
- load_catalog(): Parse the catalog CSV into structured dicts
- extract_paper_doi_from_url(): Extract DOI from a dataset's paper_url
- match_dataset_to_papers(): Find matching papers for a single dataset entry
- cross_reference(): Full batch matching of catalog → paper library
"""

import csv
import io
import json
from pathlib import Path
from typing import Optional

from lib.enrichment import extract_doi_from_url
from lib.gap_analysis import normalize_doi, normalize_title, titles_match


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------

def load_catalog(csv_path: str | Path) -> list[dict]:
    """Load the battery datasets catalog CSV into a list of dicts.

    Args:
        csv_path: Path to battery_datasets_catalog_jan17_2026.csv

    Returns:
        List of dataset dicts with all CSV columns.
    """
    path = Path(csv_path)
    content = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


def load_catalog_from_string(csv_content: str) -> list[dict]:
    """Load catalog from a CSV string (useful for testing or API ingestion).

    Args:
        csv_content: CSV content as a string

    Returns:
        List of dataset dicts.
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    return list(reader)


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------

def extract_linkable_doi(dataset: dict) -> Optional[str]:
    """Extract a normalized DOI that can link a dataset to a paper.

    Tries, in order:
    1. primary_data_doi field (the dataset's own DOI — sometimes same as paper)
    2. DOI extracted from paper_url field

    Args:
        dataset: A single dataset dict from the catalog

    Returns:
        Normalized DOI string, or None if no DOI found.
    """
    # Try primary_data_doi
    raw_doi = (dataset.get("primary_data_doi") or "").strip()
    if raw_doi:
        normalized = normalize_doi(raw_doi)
        if normalized:
            return normalized

    # Try extracting DOI from paper_url
    paper_url = (dataset.get("paper_url") or "").strip()
    if paper_url:
        extracted = extract_doi_from_url(paper_url)
        if extracted:
            return normalize_doi(extracted)

    return None


def match_dataset_to_papers(
    dataset: dict,
    papers: dict,
    paper_doi_index: dict[str, str] | None = None,
    paper_url_index: dict[str, str] | None = None,
) -> list[dict]:
    """Find papers that match a single dataset entry.

    Matching strategy (in priority order):
    1. DOI match: dataset's paper DOI matches a paper's DOI
    2. URL match: dataset's paper_url matches a paper's source_url
    3. Title match: fuzzy match on dataset title vs paper titles

    Args:
        dataset: A single dataset dict from the catalog
        papers: The paper library dict (filename -> paper metadata)
        paper_doi_index: Pre-built {normalized_doi: filename} lookup.
            If None, built on the fly.
        paper_url_index: Pre-built {url: filename} lookup.
            If None, built on the fly.

    Returns:
        List of match dicts: [{"filename": str, "match_type": str, "confidence": str}]
    """
    matches = []

    # Build indexes if not provided
    if paper_doi_index is None:
        paper_doi_index = {}
        for fname, paper in papers.items():
            doi = normalize_doi(paper.get("doi", ""))
            if doi:
                paper_doi_index[doi] = fname

    if paper_url_index is None:
        paper_url_index = {}
        for fname, paper in papers.items():
            url = (paper.get("source_url") or "").strip().lower()
            if url:
                paper_url_index[url] = fname

    seen_filenames = set()

    # Strategy 1: DOI match
    dataset_doi = extract_linkable_doi(dataset)
    if dataset_doi and dataset_doi in paper_doi_index:
        fname = paper_doi_index[dataset_doi]
        if fname not in seen_filenames:
            matches.append({
                "filename": fname,
                "match_type": "doi",
                "confidence": "high",
            })
            seen_filenames.add(fname)

    # Strategy 2: URL match
    paper_url = (dataset.get("paper_url") or "").strip().lower()
    if paper_url and paper_url in paper_url_index:
        fname = paper_url_index[paper_url]
        if fname not in seen_filenames:
            matches.append({
                "filename": fname,
                "match_type": "url",
                "confidence": "high",
            })
            seen_filenames.add(fname)

    # Strategy 3: Title match (only if no DOI/URL match found)
    if not matches:
        dataset_title = (dataset.get("title") or "").strip()
        if dataset_title:
            for fname, paper in papers.items():
                if fname in seen_filenames:
                    continue
                paper_title = (paper.get("title") or "").strip()
                if paper_title and titles_match(dataset_title, paper_title, threshold=0.85):
                    matches.append({
                        "filename": fname,
                        "match_type": "title",
                        "confidence": "medium",
                    })
                    seen_filenames.add(fname)

    return matches


# ---------------------------------------------------------------------------
# Batch cross-referencing
# ---------------------------------------------------------------------------

def cross_reference(
    catalog: list[dict],
    papers: dict,
) -> dict:
    """Match all datasets in the catalog to papers in the library.

    Args:
        catalog: List of dataset dicts (from load_catalog)
        papers: Paper library dict (filename -> paper metadata)

    Returns:
        Dict with:
        - "matches": list of {dataset_index, dataset_title, paper_matches: [...]}
        - "stats": {total_datasets, matched, unmatched, by_match_type: {...}}
    """
    # Pre-build indexes for performance
    paper_doi_index: dict[str, str] = {}
    paper_url_index: dict[str, str] = {}

    for fname, paper in papers.items():
        doi = normalize_doi(paper.get("doi", ""))
        if doi:
            paper_doi_index[doi] = fname
        url = (paper.get("source_url") or "").strip().lower()
        if url:
            paper_url_index[url] = fname

    results = []
    stats = {
        "total_datasets": len(catalog),
        "matched": 0,
        "unmatched": 0,
        "by_match_type": {"doi": 0, "url": 0, "title": 0},
    }

    for i, dataset in enumerate(catalog):
        paper_matches = match_dataset_to_papers(
            dataset, papers, paper_doi_index, paper_url_index
        )

        entry = {
            "dataset_index": i,
            "dataset_title": (dataset.get("title") or "")[:120],
            "paper_url": dataset.get("paper_url", ""),
            "paper_matches": paper_matches,
        }
        results.append(entry)

        if paper_matches:
            stats["matched"] += 1
            # Count by the best (first) match type
            stats["by_match_type"][paper_matches[0]["match_type"]] += 1
        else:
            stats["unmatched"] += 1

    return {"matches": results, "stats": stats}
