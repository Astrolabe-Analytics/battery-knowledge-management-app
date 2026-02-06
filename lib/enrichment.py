"""
Metadata enrichment functions for papers.
Handles CrossRef API, Semantic Scholar, and DOI extraction.
"""
import re
import requests
import streamlit as st
from typing import Dict, Any, Optional


def query_crossref_for_metadata(doi: str) -> dict:
    """Query CrossRef API for canonical metadata using DOI."""
    try:
        url = f"https://api.crossref.org/works/{doi}"
        headers = {
            'User-Agent': 'BatteryPaperLibrary/1.0 (mailto:researcher@example.com)'
        }
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            message = data.get('message', {})

            metadata = {}

            # Title
            titles = message.get('title', [])
            if titles:
                metadata['title'] = titles[0]

            # Authors (format as "Last, First")
            authors = []
            for author in message.get('author', []):
                given = author.get('given', '')
                family = author.get('family', '')
                if family:
                    if given:
                        authors.append(f"{family}, {given}")
                    else:
                        authors.append(family)
            metadata['authors'] = authors[:10]  # Limit to 10

            # Year
            published = message.get('published-print') or message.get('published-online')
            if published and 'date-parts' in published:
                date_parts = published['date-parts'][0]
                if date_parts:
                    metadata['year'] = str(date_parts[0])

            # Journal
            container_titles = message.get('container-title', [])
            if container_titles:
                metadata['journal'] = container_titles[0]

            # Abstract
            metadata['abstract'] = message.get('abstract', '')

            # Author keywords
            metadata['author_keywords'] = message.get('keywords', [])

            # Volume, Issue, Pages
            metadata['volume'] = message.get('volume', '')
            metadata['issue'] = message.get('issue', '')
            metadata['pages'] = message.get('page', '')

            # References
            metadata['references'] = message.get('reference', [])

            return metadata
        else:
            return {}
    except Exception as e:
        st.error(f"CrossRef API error: {e}")
        return {}


def extract_doi_from_url(url: str) -> Optional[str]:
    """Extract DOI from various publisher URL formats."""
    if not url:
        return None

    url_lower = url.lower()

    # Direct DOI URLs
    if 'doi.org/' in url_lower:
        match = re.search(r'doi\.org/(10\.\d{4,}/[^\s?#]+)', url, re.IGNORECASE)
        if match:
            doi = match.group(1).rstrip('.,;)')
            return doi

    # Nature articles
    if 'nature.com/articles/' in url_lower:
        match = re.search(r'nature\.com/articles/([^/?#]+)', url, re.IGNORECASE)
        if match:
            article_id = match.group(1).rstrip('.,;)')
            return f"10.1038/{article_id}"

    # MDPI
    if 'mdpi.com/' in url_lower:
        match = re.search(r'mdpi\.com/(\d{4}-\d{4}(?:/\d+)+)', url, re.IGNORECASE)
        if match:
            path = match.group(1).rstrip('.,;)')
            return f"10.3390/{path}"

    # IOP Science
    if 'iopscience.iop.org/article/' in url_lower:
        match = re.search(r'iopscience\.iop\.org/article/(10\.\d{4,}/[\w.-]+/[\w.-]+)', url, re.IGNORECASE)
        if match:
            doi = match.group(1).rstrip('.,;)')
            return doi

    # ScienceDirect PII
    if 'sciencedirect.com/science/article/' in url_lower and '/pii/' in url_lower:
        match = re.search(r'/pii/([A-Z0-9]+)', url, re.IGNORECASE)
        if match:
            pii = match.group(1)
            doi = lookup_doi_from_pii(pii)
            return doi

    # Cell Press PII
    if 'cell.com/' in url_lower and '/fulltext/' in url_lower:
        match = re.search(r'/fulltext/([A-Z0-9()-]+)', url, re.IGNORECASE)
        if match:
            pii = match.group(1).replace('(', '').replace(')', '')
            doi = lookup_doi_from_pii(pii)
            return doi

    # Wiley
    if 'wiley.com/doi/' in url_lower:
        match = re.search(r'wiley\.com/doi/(?:full/|abs/)?(10\.\d{4,}/[^/?#]+)', url, re.IGNORECASE)
        if match:
            doi = match.group(1).rstrip('.,;)')
            return doi

    # Springer
    if 'springer.com/article/' in url_lower:
        match = re.search(r'springer\.com/article/(10\.\d{4,}/[^/?#]+)', url, re.IGNORECASE)
        if match:
            doi = match.group(1).rstrip('.,;)')
            return doi

    # Generic DOI pattern
    match = re.search(r'(10\.\d{4,}/[^\s?#]+)', url)
    if match:
        doi = match.group(1).rstrip('.,;)')
        return doi

    return None


def lookup_doi_from_pii(pii: str) -> Optional[str]:
    """
    Look up DOI from PII - not reliable, return None.
    Enrichment will use Semantic Scholar title search instead.
    """
    return None


def find_doi_via_semantic_scholar(title: str, log_callback=None) -> Optional[str]:
    """
    Find a DOI by searching Semantic Scholar by title.

    Args:
        title: Paper title to search for
        log_callback: Optional function to call with log messages

    Returns:
        DOI string if found, None otherwise
    """
    try:
        from lib import semantic_scholar

        if log_callback:
            log_callback(f"Searching Semantic Scholar for: {title[:50]}...")

        # Use Semantic Scholar API
        results = semantic_scholar.search_papers(title, limit=5)

        if not results:
            if log_callback:
                log_callback("No results from Semantic Scholar")
            return None

        # Look for exact or very close title match in top results
        title_lower = title.lower().strip()

        for result in results:
            result_title = result.get('title', '').lower().strip()

            # Simple similarity check
            if title_lower == result_title or title_lower in result_title or result_title in title_lower:
                doi = result.get('doi')
                if doi:
                    if log_callback:
                        log_callback(f"Found DOI via Semantic Scholar: {doi}")
                    return doi

        if log_callback:
            log_callback("No matching DOI found in Semantic Scholar results")
        return None

    except Exception as e:
        if log_callback:
            log_callback(f"Semantic Scholar search error: {str(e)}")
        return None


def normalize_title_for_matching(title: str) -> str:
    """Normalize title for fuzzy matching (lowercase, remove punctuation)."""
    return re.sub(r'[^\w\s]', '', title.lower())
