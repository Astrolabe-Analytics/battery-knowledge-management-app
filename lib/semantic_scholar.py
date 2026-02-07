"""
Semantic Scholar API integration for paper search and discovery.

API Documentation: https://api.semanticscholar.org/api-docs/
Rate Limits:
- Without API key: 100 requests per 5 minutes
- With API key: 5,000 requests per 5 minutes (1 request per second enforced)

API Key Configuration:
Set the SEMANTIC_SCHOLAR_API_KEY environment variable.
Sign up for free API key at: https://www.semanticscholar.org/product/api
"""

import requests
import time
import json
import os
from typing import List, Dict, Optional
from pathlib import Path


# Rate limiting tracker
_last_request_time = 0
_min_request_interval = 2.0  # 2 seconds between requests (safer for unauthenticated)


def get_api_key() -> Optional[str]:
    """
    Get Semantic Scholar API key from environment variable.

    Returns:
        API key string or None if not set
    """
    api_key = os.environ.get('SEMANTIC_SCHOLAR_API_KEY')
    return api_key.strip() if api_key else None


def set_api_key(api_key: str) -> bool:
    """
    DEPRECATED: API key is now read from SEMANTIC_SCHOLAR_API_KEY environment variable.

    This function is kept for backward compatibility but does nothing.
    Set the environment variable SEMANTIC_SCHOLAR_API_KEY instead.

    Args:
        api_key: API key string (ignored)

    Returns:
        False (not supported)
    """
    return False


def _rate_limit(has_api_key: bool = False):
    """
    Enforce rate limiting between requests.

    Args:
        has_api_key: Whether user has API key (1 req/sec with key, 1 req/2sec without)
    """
    global _last_request_time

    # Semantic Scholar requirement: 1 request per second with API key
    interval = 1.0 if has_api_key else _min_request_interval

    current_time = time.time()
    time_since_last = current_time - _last_request_time

    if time_since_last < interval:
        time.sleep(interval - time_since_last)

    _last_request_time = time.time()


def search_papers(
    query: str,
    limit: int = 20,
    fields: List[str] = None,
    sort: str = "relevance"
) -> Dict:
    """
    Search for papers using Semantic Scholar API.

    Args:
        query: Search query string
        limit: Number of results to return (default: 20, max: 100)
        fields: List of fields to return (default: all useful fields)
        sort: Sort order - "relevance" or "citationCount" (default: relevance)

    Returns:
        Dict with 'success', 'data' (list of papers), 'total', 'error', 'has_api_key' keys
    """
    if fields is None:
        fields = [
            'title',
            'authors',
            'year',
            'abstract',
            'citationCount',
            'externalIds',
            'isOpenAccess',
            'openAccessPdf',
            'publicationDate',
            'journal',
            'venue'
        ]

    # Get API key
    api_key = get_api_key()
    has_api_key = bool(api_key)

    # Rate limit (adjust based on API key presence)
    _rate_limit(has_api_key=has_api_key)

    # Build API URL
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"

    # Build params
    params = {
        'query': query,
        'limit': min(limit, 100),  # API max is 100
        'fields': ','.join(fields)
    }

    # Add sorting if by citation count
    if sort == "citationCount":
        params['sort'] = 'citationCount:desc'

    # Build headers with API key if available
    headers = {}
    if api_key:
        headers['x-api-key'] = api_key

    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=30)

        if response.status_code == 200:
            data = response.json()

            papers = data.get('data', [])
            total = data.get('total', 0)

            return {
                'success': True,
                'data': papers,
                'total': total,
                'error': None,
                'has_api_key': has_api_key
            }
        elif response.status_code == 429:
            error_msg = 'Rate limit exceeded. '
            if not has_api_key:
                error_msg += 'Set the SEMANTIC_SCHOLAR_API_KEY environment variable for higher rate limits.'
            else:
                error_msg += 'Please wait a moment and try again.'

            return {
                'success': False,
                'data': [],
                'total': 0,
                'error': error_msg,
                'has_api_key': has_api_key
            }
        else:
            return {
                'success': False,
                'data': [],
                'total': 0,
                'error': f'API error: {response.status_code} - {response.text}',
                'has_api_key': has_api_key
            }

    except requests.exceptions.Timeout:
        return {
            'success': False,
            'data': [],
            'total': 0,
            'error': 'Request timed out. Please try again.',
            'has_api_key': has_api_key
        }
    except Exception as e:
        return {
            'success': False,
            'data': [],
            'total': 0,
            'error': f'Error: {str(e)}',
            'has_api_key': has_api_key
        }


def format_paper_for_display(paper: Dict) -> Dict:
    """
    Format Semantic Scholar paper data for display.

    Args:
        paper: Raw paper data from API

    Returns:
        Formatted paper dict
    """
    # Extract DOI
    external_ids = paper.get('externalIds', {})
    doi = external_ids.get('DOI', '') if external_ids else ''

    # Format authors
    authors = paper.get('authors', [])
    if authors:
        author_names = [a.get('name', '') for a in authors if a.get('name')]
        authors_str = ', '.join(author_names[:5])  # First 5 authors
        if len(authors) > 5:
            authors_str += f' et al. ({len(authors)} total)'
    else:
        authors_str = 'Unknown'

    # Get year
    year = paper.get('year', '')
    if not year and paper.get('publicationDate'):
        try:
            year = paper['publicationDate'].split('-')[0]
        except:
            year = ''

    # Open access PDF
    open_access_pdf = paper.get('openAccessPdf', {})
    pdf_url = open_access_pdf.get('url', '') if open_access_pdf else ''

    # Citation count
    citation_count = paper.get('citationCount', 0)

    return {
        'title': paper.get('title', 'Unknown'),
        'authors': authors_str,
        'authors_list': [a.get('name', '') for a in authors] if authors else [],
        'year': str(year) if year else '',
        'abstract': paper.get('abstract', ''),
        'doi': doi,
        'citation_count': citation_count if citation_count else 0,
        'is_open_access': paper.get('isOpenAccess', False),
        'pdf_url': pdf_url,
        'journal': paper.get('journal', {}).get('name', '') if paper.get('journal') else '',
        'venue': paper.get('venue', ''),
        'paper_id': paper.get('paperId', '')
    }


def download_pdf(pdf_url: str, save_path: Path) -> Dict:
    """
    Download PDF from URL to specified path.

    Args:
        pdf_url: URL of PDF to download
        save_path: Path to save PDF to

    Returns:
        Dict with 'success', 'message', 'path' keys
    """
    if not pdf_url:
        return {
            'success': False,
            'message': 'No PDF URL provided',
            'path': None
        }

    try:
        # Get API key for rate limiting
        api_key = get_api_key()
        has_api_key = bool(api_key)

        # Rate limit
        _rate_limit(has_api_key=has_api_key)

        # Download PDF
        response = requests.get(pdf_url, timeout=60, stream=True)

        if response.status_code == 200:
            # Ensure parent directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)

            # Save PDF
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            return {
                'success': True,
                'message': 'PDF downloaded successfully',
                'path': str(save_path)
            }
        else:
            return {
                'success': False,
                'message': f'Failed to download PDF: HTTP {response.status_code}',
                'path': None
            }

    except Exception as e:
        return {
            'success': False,
            'message': f'Error downloading PDF: {str(e)}',
            'path': None
        }


def check_papers_in_library(papers: List[Dict], library_dois: set, library_titles: set) -> List[Dict]:
    """
    Check which papers are already in the library.

    Args:
        papers: List of formatted paper dicts
        library_dois: Set of normalized DOIs in library
        library_titles: Set of normalized titles in library

    Returns:
        List of papers with 'in_library' field added
    """
    from lib.gap_analysis import normalize_doi, normalize_title, titles_match

    for paper in papers:
        in_library = False

        # Check by DOI
        if paper['doi']:
            norm_doi = normalize_doi(paper['doi'])
            if norm_doi in library_dois:
                in_library = True

        # Check by title if no DOI match
        if not in_library and paper['title']:
            norm_title = normalize_title(paper['title'])

            # Exact match
            if norm_title in library_titles:
                in_library = True
            else:
                # Fuzzy match
                for lib_title in library_titles:
                    if titles_match(norm_title, lib_title, threshold=0.9):
                        in_library = True
                        break

        paper['in_library'] = in_library

    return papers
