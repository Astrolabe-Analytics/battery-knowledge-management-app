"""
Helper functions shared across app pages.
Extracted from original monolithic app.py
"""
import streamlit as st
import json
import re
import html
import requests
from pathlib import Path
from typing import Dict, Any, Optional

def clean_html_from_text(text: str) -> str:
    """
    Remove HTML entities and tags from text.
    Converts &lt;sub&gt;4&lt;/sub&gt; to just "4"
    """
    if not text:
        return text

    # First, unescape HTML entities (&lt; -> <, &gt; -> >, etc.)
    text = html.unescape(text)

    # Then strip all HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    return text


# Page config
st.set_page_config(
    page_title="Astrolabe Research Library",
    page_icon="⚛️",
    layout="wide",
    initial_sidebar_state="expanded"
)


def load_theme_preference():
    """Load theme preference from settings file."""
    settings_file = Path("data/settings.json")
    if settings_file.exists():
        try:
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                return settings.get('theme', 'light')
        except:
            return 'light'
    return 'light'


def load_settings() -> dict:
    """Load settings from settings file."""
    settings_file = Path("data/settings.json")
    if settings_file.exists():
        try:
            with open(settings_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_settings(settings: dict):
    """Save settings to settings file."""
    settings_file = Path("data/settings.json")
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=2)


def save_theme_preference(theme: str):
    """Save theme preference to settings file."""
    settings = load_settings()
    settings['theme'] = theme
    save_settings(settings)


def get_api_key():
    """Get Anthropic API key from environment or user input (UI layer)."""
    api_key = rag.get_api_key_from_env()
    if not api_key:
        api_key = st.session_state.get("anthropic_api_key")
    if not api_key:
        with st.sidebar:
            st.warning("⚠️ Anthropic API key required for queries")
            api_key = st.text_input(
                "Enter your Anthropic API key:",
                type="password",
                help="Get your API key from https://console.anthropic.com/"
            )
            if api_key:
                st.session_state.anthropic_api_key = api_key
                st.rerun()
    return api_key


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


def save_metadata_only_paper(doi: str, crossref_metadata: dict) -> str:
    """Save metadata-only paper to ChromaDB and metadata.json"""
    import chromadb

    safe_doi = doi.replace('/', '_').replace('.', '_')
    filename = f"doi_{safe_doi}.pdf"

    # Save to metadata.json
    metadata_file = Path("data/metadata.json")
    metadata_file.parent.mkdir(parents=True, exist_ok=True)

    all_metadata = {}
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            all_metadata = json.load(f)

    all_metadata[filename] = {
        'filename': filename,
        'title': crossref_metadata.get('title', 'Unknown Title'),
        'authors': crossref_metadata.get('authors', []),
        'year': crossref_metadata.get('year', ''),
        'journal': crossref_metadata.get('journal', ''),
        'doi': doi,
        'chemistries': [],
        'topics': [],
        'application': 'general',
        'paper_type': 'experimental',
        'metadata_only': True,
        'date_added': datetime.now().isoformat(),
        'abstract': crossref_metadata.get('abstract', ''),
        'author_keywords': crossref_metadata.get('author_keywords', []),
        'volume': crossref_metadata.get('volume', ''),
        'issue': crossref_metadata.get('issue', ''),
        'pages': crossref_metadata.get('pages', ''),
        'source_url': '',
        'notes': '',
        'references': crossref_metadata.get('references', [])
    }

    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, indent=2, ensure_ascii=False)

    # Add to ChromaDB using the DatabaseClient to ensure consistency
    from lib.rag import DatabaseClient

    # First clear any cached collection to force a fresh connection
    DatabaseClient.clear_cache()

    # Now get a fresh collection reference
    collection = DatabaseClient.get_collection()

    doc_id = f"{filename}_metadata_only"
    try:
        collection.delete(ids=[doc_id])
    except:
        pass

    collection.add(
        documents=[f"Metadata-only: {crossref_metadata.get('title', '')}. DOI: {doi}"],
        metadatas=[{
            'filename': filename,
            'page_num': 0,
            'section_name': 'metadata_only',
            'title': crossref_metadata.get('title', ''),
            'authors': ';'.join(crossref_metadata.get('authors', [])) if crossref_metadata.get('authors') else '',
            'year': crossref_metadata.get('year', ''),
            'journal': crossref_metadata.get('journal', ''),
            'doi': doi,
            'chemistries': '',
            'topics': '',
            'application': 'general',
            'paper_type': 'experimental',
            'abstract': crossref_metadata.get('abstract', ''),
            'author_keywords': ';'.join(crossref_metadata.get('author_keywords', [])),
            'volume': crossref_metadata.get('volume', ''),
            'issue': crossref_metadata.get('issue', ''),
            'pages': crossref_metadata.get('pages', ''),
            'date_added': datetime.now().isoformat(),
            'source_url': ''
        }],
        ids=[doc_id]
    )

    # Clear cache again so next get_paper_library() call sees the new paper
    DatabaseClient.clear_cache()

    return filename


def add_paper_with_pdf_search(doi: str, title: str, authors: str, year: str, url: str = '') -> dict:
    """
    Add paper to library, attempting to find and download open access PDF.

    Args:
        doi: Paper DOI
        title: Paper title
        authors: Paper authors string
        year: Publication year
        url: Paper URL (optional)

    Returns:
        Dict with 'success', 'message', 'pdf_found' keys
    """
    try:
        # Step 1: Get metadata from CrossRef if we have DOI
        if doi:
            crossref_metadata = query_crossref_for_metadata(doi)
            if not crossref_metadata or not crossref_metadata.get('title'):
                # Fallback to provided metadata
                crossref_metadata = {
                    'title': title,
                    'authors': [authors] if authors else [],
                    'year': year
                }
        else:
            # No DOI - use provided metadata
            crossref_metadata = {
                'title': title,
                'authors': [authors] if authors else [],
                'year': year
            }

        # Step 2: Try to find open access PDF via Semantic Scholar
        pdf_url = None
        pdf_found = False

        if doi:
            # Search Semantic Scholar for this DOI
            try:
                search_result = semantic_scholar.search_papers(
                    query=f'doi:{doi}',
                    limit=1
                )

                if search_result['success'] and search_result['data']:
                    paper_data = search_result['data'][0]
                    formatted = semantic_scholar.format_paper_for_display(paper_data)

                    if formatted['is_open_access'] and formatted['pdf_url']:
                        pdf_url = formatted['pdf_url']
                        pdf_found = True
            except:
                pass  # Continue even if Semantic Scholar fails

        # Step 3: Try Unpaywall as fallback (if still no PDF)
        if not pdf_found and doi:
            try:
                import requests
                unpaywall_url = f"https://api.unpaywall.org/v2/{doi}?email=user@example.com"
                response = requests.get(unpaywall_url, timeout=10)

                if response.status_code == 200:
                    unpaywall_data = response.json()
                    if unpaywall_data.get('is_oa') and unpaywall_data.get('best_oa_location'):
                        oa_location = unpaywall_data['best_oa_location']
                        if oa_location.get('url_for_pdf'):
                            pdf_url = oa_location['url_for_pdf']
                            pdf_found = True
            except:
                pass  # Continue even if Unpaywall fails

        # Step 4: Download PDF if found
        filename = None
        if pdf_found and pdf_url:
            # Create safe filename
            safe_title = re.sub(r'[^\w\s-]', '', title[:50])
            safe_title = re.sub(r'[-\s]+', '_', safe_title)
            filename = f"{safe_title}.pdf"
            pdf_path = Path("papers") / filename

            download_result = semantic_scholar.download_pdf(pdf_url, pdf_path)

            if not download_result['success']:
                # Download failed, fall back to metadata-only
                pdf_found = False
                filename = None

        # Step 5: Save metadata
        if not filename:
            # Metadata-only
            if doi:
                safe_doi = doi.replace('/', '_').replace('.', '_')
                filename = f"doi_{safe_doi}.pdf"
            else:
                safe_title = re.sub(r'[^\w\s-]', '', title[:50])
                safe_title = re.sub(r'[-\s]+', '_', safe_title)
                filename = f"{safe_title}.pdf"

        # Save to metadata.json
        metadata_file = Path("data/metadata.json")
        metadata_file.parent.mkdir(parents=True, exist_ok=True)

        all_metadata = {}
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                all_metadata = json.load(f)

        # Determine PDF status
        pdf_status = "available" if pdf_found else "needs_pdf"

        all_metadata[filename] = {
            'filename': filename,
            'title': crossref_metadata.get('title', title),
            'authors': crossref_metadata.get('authors', [authors] if authors else []),
            'year': crossref_metadata.get('year', year),
            'journal': crossref_metadata.get('journal', ''),
            'doi': doi,
            'chemistries': [],
            'topics': [],
            'application': 'general',
            'paper_type': 'experimental',
            'metadata_only': not pdf_found,
            'pdf_status': pdf_status,
            'date_added': datetime.now().isoformat(),
            'abstract': crossref_metadata.get('abstract', ''),
            'author_keywords': crossref_metadata.get('author_keywords', []),
            'volume': crossref_metadata.get('volume', ''),
            'issue': crossref_metadata.get('issue', ''),
            'pages': crossref_metadata.get('pages', ''),
            'source_url': url,
            'notes': '',
            'references': crossref_metadata.get('references', [])
        }

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, indent=2, ensure_ascii=False)

        # Add to ChromaDB
        from lib.rag import DatabaseClient
        DatabaseClient.clear_cache()
        collection = DatabaseClient.get_collection()

        doc_id = f"{filename}_metadata"
        try:
            collection.delete(ids=[doc_id])
        except:
            pass

        collection.add(
            documents=[f"Metadata: {crossref_metadata.get('title', title)}. DOI: {doi}"],
            metadatas=[{
                'filename': filename,
                'page_num': 0,
                'paper_type': 'experimental',
                'application': 'general',
                'chemistries': '',
                'topics': '',
                'section_name': 'metadata',
                'abstract': crossref_metadata.get('abstract', ''),
                'author_keywords': ';'.join(crossref_metadata.get('author_keywords', [])),
                'title': crossref_metadata.get('title', title),
                'authors': '; '.join(crossref_metadata.get('authors', [])) if isinstance(crossref_metadata.get('authors'), list) else str(crossref_metadata.get('authors', '')),
                'year': str(crossref_metadata.get('year', year)),
                'journal': crossref_metadata.get('journal', ''),
                'doi': doi
            }],
            ids=[doc_id]
        )

        DatabaseClient.clear_cache()

        return {
            'success': True,
            'message': f"Added: {title[:50]}..." if len(title) > 50 else title,
            'pdf_found': pdf_found
        }

    except Exception as e:
        return {
            'success': False,
            'message': f"Failed to add {title[:30]}...: {str(e)}",
            'pdf_found': False
        }


def extract_doi_from_url(url: str) -> str:
    """
    Extract DOI from various publisher URL formats.

    Args:
        url: URL string that might contain a DOI

    Returns:
        Extracted DOI or None
    """
    if not url:
        return None

    url_lower = url.lower()

    # Direct DOI URLs
    if 'doi.org/' in url_lower:
        match = re.search(r'doi\.org/(10\.\d{4,}/[^\s?#]+)', url, re.IGNORECASE)
        if match:
            doi = match.group(1).rstrip('.,;)')
            return doi

    # Nature articles: nature.com/articles/s41560-019-0356-8 → 10.1038/s41560-019-0356-8
    if 'nature.com/articles/' in url_lower:
        match = re.search(r'nature\.com/articles/([^/?#]+)', url, re.IGNORECASE)
        if match:
            article_id = match.group(1).rstrip('.,;)')
            return f"10.1038/{article_id}"

    # MDPI: mdpi.com/2313-0105/8/10/151 → 10.3390/2313-0105/8/10/151
    if 'mdpi.com/' in url_lower:
        match = re.search(r'mdpi\.com/(\d{4}-\d{4}(?:/\d+)+)', url, re.IGNORECASE)
        if match:
            path = match.group(1).rstrip('.,;)')
            return f"10.3390/{path}"

    # IOP Science: iopscience.iop.org/article/10.1149/1945-7111/abae37 → 10.1149/1945-7111/abae37
    if 'iopscience.iop.org/article/' in url_lower:
        match = re.search(r'iopscience\.iop\.org/article/(10\.\d{4,}/[\w.-]+/[\w.-]+)', url, re.IGNORECASE)
        if match:
            doi = match.group(1).rstrip('.,;)')
            return doi

    # ScienceDirect PII: sciencedirect.com/science/article/pii/S2352152X24044748
    if 'sciencedirect.com/science/article/' in url_lower and '/pii/' in url_lower:
        match = re.search(r'/pii/([A-Z0-9]+)', url, re.IGNORECASE)
        if match:
            pii = match.group(1)
            # Try to look up DOI from PII via CrossRef
            doi = lookup_doi_from_pii(pii)
            if doi:
                return doi

    # Cell Press PII: cell.com/joule/fulltext/S2542-4351(24)00510-5
    if 'cell.com/' in url_lower and '/fulltext/' in url_lower:
        match = re.search(r'/fulltext/([A-Z0-9()-]+)', url, re.IGNORECASE)
        if match:
            pii = match.group(1).replace('(', '').replace(')', '')
            # Try to look up DOI from PII via CrossRef
            doi = lookup_doi_from_pii(pii)
            if doi:
                return doi

    # Wiley: onlinelibrary.wiley.com/doi/10.1002/adma.202402024 → 10.1002/adma.202402024
    if 'wiley.com/doi/' in url_lower:
        match = re.search(r'wiley\.com/doi/(?:full/|abs/)?(10\.\d{4,}/[^/?#]+)', url, re.IGNORECASE)
        if match:
            doi = match.group(1).rstrip('.,;)')
            return doi

    # Springer: link.springer.com/article/10.1007/s12274-024-6447-x → 10.1007/s12274-024-6447-x
    if 'springer.com/article/' in url_lower:
        match = re.search(r'springer\.com/article/(10\.\d{4,}/[^/?#]+)', url, re.IGNORECASE)
        if match:
            doi = match.group(1).rstrip('.,;)')
            return doi

    # Generic DOI pattern in URL (fallback)
    match = re.search(r'(10\.\d{4,}/[^\s?#]+)', url)
    if match:
        doi = match.group(1).rstrip('.,;)')
        return doi

    return None


def lookup_doi_from_pii(pii: str) -> str:
    """
    Look up DOI from PII (Publisher Item Identifier).

    For Elsevier papers (ScienceDirect, Cell), PII can often be converted to DOI:
    - Format: S + ISSN (8 chars) + year (2 digits) + serial (5-6 digits)
    - Example: S2352152X24044748 might map to specific DOI pattern

    However, there's no direct PII->DOI conversion API. Best approach:
    Return None and let Semantic Scholar handle it via title search.

    Args:
        pii: Publisher Item Identifier (e.g., S2352152X24044748)

    Returns:
        DOI if found, None otherwise
    """
    # PII to DOI lookup is unreliable without the publisher's internal database
    # Better to return None and fall back to Semantic Scholar title search
    # which has better coverage and accuracy
    return None


def find_doi_via_semantic_scholar(title: str, log_callback=None) -> str:
    """
    Find DOI by searching Semantic Scholar by paper title

    Args:
        title: Paper title to search for
        log_callback: Optional callback function for logging

    Returns:
        DOI string if found, empty string otherwise
    """
    import requests
    import time

    def log(msg):
        if log_callback:
            log_callback(msg)

    if not title:
        log("  [Semantic Scholar] Skipped: No title provided")
        return ''

    try:
        log(f"  [Semantic Scholar] Searching for: {title[:60]}...")

        # Semantic Scholar search API
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            'query': title.strip(),
            'limit': 3,
            'fields': 'title,externalIds'
        }

        headers = {'User-Agent': 'AstrolabePaperDB/1.0'}

        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code == 429:
            log("  [Semantic Scholar] Rate limited (429) - skipping")
            return ''

        response.raise_for_status()
        data = response.json()

        if 'data' not in data or not data['data']:
            log("  [Semantic Scholar] No results found")
            return ''

        log(f"  [Semantic Scholar] Found {len(data['data'])} result(s)")

        # Check top results for title match
        def normalize(s):
            return re.sub(r'[^\w\s]', '', s.lower()).strip()

        normalized_query = normalize(title)

        for i, paper in enumerate(data['data'], 1):
            result_title = paper.get('title', '')
            normalized_result = normalize(result_title)

            # Check for exact or very close match
            if normalized_query == normalized_result:
                log(f"  [Semantic Scholar] Match found: {result_title[:50]}...")

                external_ids = paper.get('externalIds', {})
                doi = external_ids.get('DOI', '')

                if doi:
                    log(f"  [Semantic Scholar] DOI: {doi}")
                    return doi
                else:
                    log(f"  [Semantic Scholar] No DOI in record")
                    return ''

        log("  [Semantic Scholar] No exact title match in results")
        return ''

    except requests.exceptions.Timeout:
        log("  [Semantic Scholar] Request timeout")
        return ''
    except requests.exceptions.RequestException as e:
        log(f"  [Semantic Scholar] Error: {type(e).__name__}")
        return ''
    except Exception as e:
        log(f"  [Semantic Scholar] Unexpected error: {type(e).__name__}")
        return ''


def normalize_title_for_matching(title: str) -> str:
    """Normalize title for duplicate detection."""
    if not title:
        return ""

    # Lowercase, remove punctuation, collapse whitespace
    normalized = title.lower()
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def is_paper_in_library(title: str, doi: str, existing_papers: list) -> bool:
    """
    Check if paper is already in library.

    Args:
        title: Paper title
        doi: Paper DOI
        existing_papers: List of existing papers from library

    Returns:
        True if paper is duplicate, False otherwise
    """
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


def get_column_value_case_insensitive(row_dict: dict, *possible_names: str) -> str:
    """
    Get value from dict with case-insensitive column name matching.

    Args:
        row_dict: Dictionary with column data
        possible_names: Possible column names to try

    Returns:
        Value from first matching column, or empty string
    """
    # Create lowercase mapping of all keys
    lowercase_map = {k.lower(): k for k in row_dict.keys()}

    # Try each possible name (case-insensitive)
    for name in possible_names:
        lowercase_name = name.lower()
        if lowercase_name in lowercase_map:
            actual_key = lowercase_map[lowercase_name]
            value = row_dict.get(actual_key, '')
            if value:
                return str(value).strip()

    return ''


# ===== CANONICAL IMPORT SCHEMA =====

# Define our canonical metadata fields
CANONICAL_SCHEMA = {
    'title': str,
    'authors': str,
    'year': str,
    'journal': str,
    'doi': str,
    'url': str,
    'abstract': str,
    'chemistry': str,
    'topics': str,
    'tags': str,
    'paper_type': str,
    'application': str,
    'pdf_status': str,
    'date_added': str,
    'notes': str
}

# Column mappings for different import sources
IMPORT_SOURCE_MAPPINGS = {
    'notion_csv': {
        'Title': 'title',
        'Authors / Orgs': 'authors',
        'Authors': 'authors',
        'Publication Year': 'year',
        'Year': 'year',
        'Journal': 'journal',
        'URL': 'url',
        'url': 'url',
        'Tags': 'tags',
        'tags': 'tags',
        'Abstract/Notes': 'abstract',
        'Abstract': 'abstract',
        'Notes': 'notes',
        'DOI': 'doi',
        'doi': 'doi'
    },
    'battery_datasets': {
        'title': 'title',
        'Title': 'title',
        'authors': 'authors',
        'Authors': 'authors',
        'year': 'year',
        'Year': 'year',
        'journal': 'journal',
        'Journal': 'journal',
        'paper_url': 'url',
        'chemistry': 'chemistry',
        'Chemistry': 'chemistry',
        'tags': 'tags',
        'Tags': 'tags',
        'doi': 'doi',
        'DOI': 'doi'
    },
    'generic': {
        # Fallback mappings - tries common variations
        'title': 'title',
        'Title': 'title',
        'TITLE': 'title',
        'authors': 'authors',
        'Authors': 'authors',
        'AUTHORS': 'authors',
        'Author': 'authors',
        'year': 'year',
        'Year': 'year',
        'YEAR': 'year',
        'journal': 'journal',
        'Journal': 'journal',
        'JOURNAL': 'journal',
        'url': 'url',
        'URL': 'url',
        'doi': 'doi',
        'DOI': 'doi',
        'abstract': 'abstract',
        'Abstract': 'abstract',
        'tags': 'tags',
        'Tags': 'tags',
        'chemistry': 'chemistry',
        'Chemistry': 'chemistry'
    }
}


def detect_import_source(columns: list) -> str:
    """
    Detect the import source type based on column names.

    Args:
        columns: List of column names from the file

    Returns:
        Source type: 'notion_csv', 'battery_datasets', or 'generic'
    """
    columns_lower = [c.lower() for c in columns]

    # Check for Battery Datasets signature
    if 'paper_url' in columns_lower or 'chemistry' in columns_lower:
        return 'battery_datasets'

    # Check for Notion signature
    if 'authors / orgs' in columns_lower or 'abstract/notes' in columns_lower:
        return 'notion_csv'

    # Default to generic
    return 'generic'


def normalize_to_canonical_schema(row_data: dict, source_type: str = None) -> dict:
    """
    Convert a row from any import source to our canonical schema.

    Args:
        row_data: Dictionary with source column names
        source_type: Type of source ('notion_csv', 'battery_datasets', 'generic')
                    If None, will auto-detect

    Returns:
        Dictionary with canonical field names
    """
    if source_type is None:
        source_type = detect_import_source(list(row_data.keys()))

    # Get the mapping for this source
    mapping = IMPORT_SOURCE_MAPPINGS.get(source_type, IMPORT_SOURCE_MAPPINGS['generic'])

    # Create canonical record
    canonical = {}

    # Map each source column to canonical field
    for source_col, canonical_field in mapping.items():
        if source_col in row_data and row_data[source_col]:
            value = str(row_data[source_col]).strip()
            if value:
                canonical[canonical_field] = value

    # Ensure all canonical fields exist (even if empty)
    for field in CANONICAL_SCHEMA.keys():
        if field not in canonical:
            canonical[field] = ''

    return canonical


def enrich_from_crossref(canonical_data: dict) -> dict:
    """
    Enrich missing fields using CrossRef API based on DOI or URL.

    Args:
        canonical_data: Dictionary with canonical fields

    Returns:
        Enriched dictionary with additional fields from CrossRef
    """
    # Extract DOI from URL if not present
    if not canonical_data['doi'] and canonical_data['url']:
        canonical_data['doi'] = extract_doi_from_url(canonical_data['url'])

    # If we have a DOI, try to fetch metadata
    if canonical_data['doi']:
        try:
            crossref_metadata = query_crossref_for_metadata(canonical_data['doi'])

            if crossref_metadata:
                # Fill in missing fields from CrossRef
                if not canonical_data['title'] and crossref_metadata.get('title'):
                    canonical_data['title'] = crossref_metadata['title']

                if not canonical_data['authors'] and crossref_metadata.get('authors'):
                    canonical_data['authors'] = ', '.join(crossref_metadata['authors'])

                if not canonical_data['year'] and crossref_metadata.get('year'):
                    canonical_data['year'] = str(crossref_metadata['year'])

                if not canonical_data['journal'] and crossref_metadata.get('journal'):
                    canonical_data['journal'] = crossref_metadata['journal']

                if not canonical_data['abstract'] and crossref_metadata.get('abstract'):
                    canonical_data['abstract'] = crossref_metadata['abstract']
        except Exception as e:
            # CrossRef enrichment failed, continue with what we have
            pass

    return canonical_data


def enrich_library_metadata(max_papers: int = None, progress_callback=None) -> dict:
    """
    Enrich metadata for papers in library that have URLs but missing key fields.

    Args:
        max_papers: Maximum number of papers to enrich (None = all)
        progress_callback: Optional callback function for progress updates

    Returns:
        Dict with enrichment statistics
    """
    import time

    # Load metadata
    metadata_file = Path("data/metadata.json")
    if not metadata_file.exists():
        return {'success': False, 'message': 'No metadata file found', 'enriched': 0}

    with open(metadata_file, 'r', encoding='utf-8') as f:
        all_metadata = json.load(f)

    # Find papers needing enrichment (have URL/DOI but missing key fields)
    papers_to_enrich = []
    for filename, paper in all_metadata.items():
        url = paper.get('url', '') or paper.get('source_url', '')
        doi = paper.get('doi', '')

        # Check if has URL or DOI
        if url or doi:
            # Check if missing key metadata
            missing_authors = not paper.get('authors') or paper.get('authors') == []
            missing_year = not paper.get('year')
            missing_journal = not paper.get('journal')

            if missing_authors or missing_year or missing_journal:
                papers_to_enrich.append((filename, paper, url, doi))

    if not papers_to_enrich:
        return {'success': True, 'message': 'No papers need enrichment', 'enriched': 0}

    # Limit if specified
    if max_papers:
        papers_to_enrich = papers_to_enrich[:max_papers]

    # Enrich papers
    enriched_count = 0
    failed_count = 0
    enrichment_logs = []  # Store logs for debugging

    def log(msg):
        """Helper to log messages"""
        enrichment_logs.append(msg)
        if progress_callback:
            progress_callback(-1, -1, msg)  # Special callback for logs

    for idx, (filename, paper, url, doi) in enumerate(papers_to_enrich):
        try:
            title = paper.get('title', filename)
            if progress_callback:
                progress_callback(idx + 1, len(papers_to_enrich), title)

            log(f"\n[{idx + 1}/{len(papers_to_enrich)}] {title[:60]}...")

            # Step 1: Extract DOI from URL if not present
            if not doi and url:
                log(f"  [DOI Extraction] URL: {url[:70]}...")
                doi = extract_doi_from_url(url)
                if doi:
                    log(f"  [DOI Extraction] Found: {doi}")
                    all_metadata[filename]['doi'] = doi
                else:
                    log(f"  [DOI Extraction] Failed: No DOI pattern in URL")

            # Step 2: If no DOI, try Semantic Scholar as fallback
            if not doi:
                log(f"  [Fallback] Trying Semantic Scholar by title...")
                doi = find_doi_via_semantic_scholar(title, log_callback=log)
                if doi:
                    all_metadata[filename]['doi'] = doi
                    # Rate limit for Semantic Scholar API (100 requests per 5 min)
                    time.sleep(1.5)

            # Step 3: Query CrossRef if we have DOI
            if doi:
                log(f"  [CrossRef] Querying for DOI: {doi}")
                crossref_metadata = query_crossref_for_metadata(doi)

                if crossref_metadata:
                    log(f"  [CrossRef] Received metadata with {len(crossref_metadata)} fields")
                    updated_fields = []

                    # Update missing fields
                    if not all_metadata[filename].get('authors') or all_metadata[filename].get('authors') == []:
                        if crossref_metadata.get('authors'):
                            all_metadata[filename]['authors'] = crossref_metadata['authors']
                            updated_fields.append('authors')

                    if not all_metadata[filename].get('year'):
                        if crossref_metadata.get('year'):
                            all_metadata[filename]['year'] = str(crossref_metadata['year'])
                            updated_fields.append('year')

                    if not all_metadata[filename].get('journal'):
                        if crossref_metadata.get('journal'):
                            all_metadata[filename]['journal'] = crossref_metadata['journal']
                            updated_fields.append('journal')

                    if not all_metadata[filename].get('abstract'):
                        if crossref_metadata.get('abstract'):
                            all_metadata[filename]['abstract'] = crossref_metadata['abstract']
                            updated_fields.append('abstract')

                    if not all_metadata[filename].get('volume'):
                        if crossref_metadata.get('volume'):
                            all_metadata[filename]['volume'] = crossref_metadata['volume']
                            updated_fields.append('volume')

                    if not all_metadata[filename].get('issue'):
                        if crossref_metadata.get('issue'):
                            all_metadata[filename]['issue'] = crossref_metadata['issue']
                            updated_fields.append('issue')

                    if not all_metadata[filename].get('pages'):
                        if crossref_metadata.get('pages'):
                            all_metadata[filename]['pages'] = crossref_metadata['pages']
                            updated_fields.append('pages')

                    if updated_fields:
                        log(f"  [Success] Updated: {', '.join(updated_fields)}")
                        enriched_count += 1
                    else:
                        log(f"  [Skipped] All fields already present")
                        failed_count += 1
                else:
                    log(f"  [CrossRef] Failed: No metadata returned")
                    failed_count += 1
            else:
                log(f"  [Failed] No DOI available - cannot enrich")
                failed_count += 1

            # Rate limiting - 1 second delay between papers
            time.sleep(1.0)

        except Exception as e:
            log(f"  [Error] {type(e).__name__}: {str(e)}")
            failed_count += 1

    # Save updated metadata to metadata.json
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, indent=2, ensure_ascii=False)

    # Update ChromaDB with enriched metadata
    from lib.rag import DatabaseClient
    DatabaseClient.clear_cache()
    collection = DatabaseClient.get_collection()

    # Update each enriched paper in ChromaDB
    for filename, paper, url, doi in papers_to_enrich:
        enriched_paper = all_metadata[filename]
        doc_id = f"{filename}_metadata"

        # Get existing metadata document
        try:
            existing_doc = collection.get(ids=[doc_id], include=['metadatas'])
            if existing_doc and existing_doc['metadatas']:
                # Update the metadata document with enriched fields
                authors = enriched_paper.get('authors', [])
                if isinstance(authors, list):
                    authors_str = '; '.join(authors)
                else:
                    authors_str = str(authors)

                # Delete old and add updated
                collection.delete(ids=[doc_id])
                collection.add(
                    documents=[f"Metadata: {enriched_paper.get('title', '')}. DOI: {enriched_paper.get('doi', '')}"],
                    metadatas=[{
                        'filename': filename,
                        'page_num': 0,
                        'paper_type': enriched_paper.get('paper_type', 'experimental'),
                        'application': enriched_paper.get('application', 'general'),
                        'chemistries': ','.join(enriched_paper.get('chemistries', [])) if isinstance(enriched_paper.get('chemistries'), list) else '',
                        'topics': ','.join(enriched_paper.get('topics', [])) if isinstance(enriched_paper.get('topics'), list) else '',
                        'section_name': 'metadata',
                        'abstract': enriched_paper.get('abstract', ''),
                        'author_keywords': ';'.join(enriched_paper.get('author_keywords', [])) if isinstance(enriched_paper.get('author_keywords'), list) else '',
                        'title': enriched_paper.get('title', ''),
                        'authors': authors_str,
                        'year': str(enriched_paper.get('year', '')),
                        'journal': enriched_paper.get('journal', ''),
                        'doi': enriched_paper.get('doi', '')
                    }],
                    ids=[doc_id]
                )
        except:
            pass  # If document doesn't exist in ChromaDB, skip

    # Clear cache again after updates
    DatabaseClient.clear_cache()

    # Create appropriate message
    if enriched_count == 0 and failed_count == 0:
        message = "No papers were enriched"
    elif enriched_count == 0:
        message = f"Failed to enrich {failed_count} paper(s)"
    elif failed_count == 0:
        message = f"Successfully enriched {enriched_count} paper(s)"
    else:
        message = f"Enriched {enriched_count} paper(s), failed {failed_count}"

    return {
        'success': True,
        'enriched': enriched_count,
        'failed': failed_count,
        'total': len(papers_to_enrich),
        'message': message,
        'logs': enrichment_logs  # Include detailed logs for debugging
    }


def import_csv_papers(csv_papers: list, batch_size: int, skip_existing: bool, existing_papers: list):
    """
    Import papers from CSV with progress tracking and rate limiting.

    Args:
        csv_papers: List of paper dicts from CSV
        batch_size: Number of papers to import
        skip_existing: Whether to skip duplicates
        existing_papers: List of existing papers in library
    """
    import time

    # Debug: Show column names and detected source type
    if csv_papers:
        columns = list(csv_papers[0].keys())
        source_type = detect_import_source(columns)

        st.info(f"📋 **Import Source Detected:** {source_type.replace('_', ' ').title()}")
        st.caption(f"**Columns:** {', '.join(columns)}")

        # Show field mapping
        with st.expander("🔍 Column Mapping Preview"):
            sample = normalize_to_canonical_schema(csv_papers[0], source_type)
            mapped_fields = {k: v for k, v in sample.items() if v}
            if mapped_fields:
                st.json(mapped_fields)

    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()

    imported = 0
    skipped = 0
    failed = 0
    import_logs = []  # Collect detailed logs

    # Process papers in batch
    papers_to_process = csv_papers[:batch_size]

    for idx, csv_paper in enumerate(papers_to_process):
        try:
            # Update progress
            progress = (idx + 1) / len(papers_to_process)
            progress_bar.progress(progress)

            # Normalize to canonical schema
            canonical = normalize_to_canonical_schema(csv_paper)

            # Enrich with CrossRef if we have URL/DOI
            canonical = enrich_from_crossref(canonical)

            # Extract fields
            title = canonical['title']
            url = canonical['url']
            authors = canonical['authors']
            year = canonical['year']
            journal = canonical['journal']
            abstract = canonical['abstract']
            tags = canonical['tags']
            doi = canonical['doi']
            chemistry = canonical['chemistry']

            # Skip if no title
            if not title:
                import_logs.append(f"⚠️ Row {idx + 1}: No title, skipping")
                skipped += 1
                time.sleep(0.5)
                continue

            # Check for duplicates
            if skip_existing and is_paper_in_library(title, doi, existing_papers):
                status_text.text(f"Importing paper {idx + 1} of {len(papers_to_process)}: {title[:50]}...")
                import_logs.append(f"⏭️ Skipped: {title[:60]}... (already in library)")
                skipped += 1
                time.sleep(0.5)
                continue

            # Show current paper
            status_text.text(f"Importing paper {idx + 1} of {len(papers_to_process)}: {title[:50]}...")

            result = add_paper_with_pdf_search(
                doi=doi or '',
                title=title,
                authors=authors,
                year=year,
                url=url
            )

            if result['success']:
                pdf_icon = "📄" if result['pdf_found'] else "📝"
                import_logs.append(f"✓ {pdf_icon} Added: {title[:60]}...")
                imported += 1
            else:
                import_logs.append(f"❌ Failed: {title[:60]}... - {result['message']}")
                failed += 1

            # Rate limiting: 2-3 seconds between papers (for CrossRef + Unpaywall)
            time.sleep(2.5)

        except Exception as e:
            import traceback
            error_msg = f"❌ Error processing row {idx + 1}: {type(e).__name__}: {str(e)}"
            import_logs.append(error_msg)
            import_logs.append(f"   Traceback: {traceback.format_exc()}")
            failed += 1
            time.sleep(1)

    # Clear progress indicators
    progress_bar.empty()
    status_text.empty()

    # Summary message
    summary_parts = []
    if imported > 0:
        summary_parts.append(f"✅ Imported {imported} paper{'s' if imported != 1 else ''}")
    if skipped > 0:
        summary_parts.append(f"⏭️ {skipped} skipped")
    if failed > 0:
        summary_parts.append(f"❌ {failed} failed")

    if imported > 0:
        st.success(". ".join(summary_parts) + ".")
    elif len(papers_to_process) > 0:
        st.info(". ".join(summary_parts) + ".")
    else:
        st.warning("No papers to import")

    # Details in expander
    if import_logs:
        with st.expander("Show details"):
            for log in import_logs:
                st.text(log)

    if imported > 0:
        st.info("Refreshing app to show new papers...")
        time.sleep(2)
        st.rerun()


def update_paper_metadata(filename: str, doi: str, crossref_metadata: dict):
    """Update paper metadata in metadata.json and ChromaDB."""
    metadata_file = Path("data/metadata.json")

    # Load existing metadata
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            all_metadata = json.load(f)
    else:
        all_metadata = {}

    # Update metadata for this paper
    if filename in all_metadata:
        # Update with CrossRef data
        all_metadata[filename]['doi'] = doi
        if crossref_metadata:
            all_metadata[filename]['title'] = crossref_metadata.get('title', all_metadata[filename].get('title', ''))
            all_metadata[filename]['authors'] = crossref_metadata.get('authors', all_metadata[filename].get('authors', []))
            all_metadata[filename]['year'] = crossref_metadata.get('year', all_metadata[filename].get('year', ''))
            all_metadata[filename]['journal'] = crossref_metadata.get('journal', all_metadata[filename].get('journal', ''))

        # Save updated metadata
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, indent=2, ensure_ascii=False)

        # Update ChromaDB
        update_chromadb_metadata(filename, all_metadata[filename])

        return True
    return False


def update_chromadb_metadata(filename: str, paper_metadata: dict):
    """Update metadata for all chunks of a paper in ChromaDB."""
    try:
        collection = rag.DatabaseClient.get_collection()

        # Get all chunks for this paper
        results = collection.get(
            where={"filename": filename},
            include=["metadatas"]
        )

        if not results['ids']:
            return

        # Update metadata for each chunk
        updated_metadatas = []
        for metadata in results['metadatas']:
            metadata['doi'] = paper_metadata.get('doi', '')
            metadata['title'] = paper_metadata.get('title', '')
            metadata['authors'] = ';'.join(paper_metadata.get('authors', []))
            metadata['year'] = paper_metadata.get('year', '')
            metadata['journal'] = paper_metadata.get('journal', '')
            updated_metadatas.append(metadata)

        # Update in ChromaDB
        collection.update(
            ids=results['ids'],
            metadatas=updated_metadatas
        )
    except Exception as e:
        st.error(f"Error updating ChromaDB: {e}")


def main():
    # Import modules used throughout main() to avoid UnboundLocalError
    import re
    from pathlib import Path

    # Initialize session state
    if "selected_paper" not in st.session_state:
        st.session_state.selected_paper = None
    if "query_result" not in st.session_state:
        st.session_state.query_result = None
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "Library"

    # Initialize theme
    if "theme" not in st.session_state:
        st.session_state.theme = load_theme_preference()

    # Initialize databases
    read_status.init_db()
    query_history.init_db()
    collections._get_connection().close()  # Initialize collections DB

    # Apply professional CSS styling
    current_theme = st.session_state.theme
    st.markdown(styles.get_professional_css(current_theme), unsafe_allow_html=True)

    # Header - Clean and professional
    st.markdown("""
        <div class="app-header">
            <h1 class="app-title">Astrolabe Research Library</h1>
            <p class="app-subtitle">Battery research papers with AI-powered search</p>
        </div>
    """, unsafe_allow_html=True)

    # Load resources using backend with session state caching
    # Cache papers to avoid reloading ChromaDB on every rerun
    if 'cached_papers' not in st.session_state or st.session_state.get('reload_papers', False):
        try:
            st.session_state.cached_papers = rag.get_paper_library()
            st.session_state.cached_filter_options = rag.get_filter_options()
            st.session_state.cached_total_chunks = rag.get_collection_count()
            st.session_state.reload_papers = False
        except (FileNotFoundError, RuntimeError) as e:
            st.error(str(e))
            st.info("Please run `python scripts/ingest.py` first to create the database")
            st.stop()

    papers = st.session_state.cached_papers
    filter_options = st.session_state.cached_filter_options
    total_chunks = st.session_state.cached_total_chunks

    # Sidebar - Simplified and professional
    with st.sidebar:
        # Quick stats with breakdown
        st.subheader("Library Stats")

        # Categorize papers into three groups
        total_papers = len(papers)
        complete_papers = 0
        metadata_only_papers = 0
        incomplete_papers = 0

        for paper in papers:
            # Check if metadata is complete
            has_title = bool(paper.get('title', '').strip())
            has_authors = bool(paper.get('authors') and paper.get('authors') != [])
            has_year = bool(paper.get('year', '').strip())
            has_journal = bool(paper.get('journal', '').strip())

            metadata_complete = has_title and has_authors and has_year and has_journal

            # Check if PDF exists
            filename = paper.get('filename', '')
            has_pdf = False
            if filename:
                pdf_path = Path("papers") / filename
                has_pdf = pdf_path.exists()

            # Categorize
            if metadata_complete and has_pdf:
                complete_papers += 1
            elif metadata_complete and not has_pdf:
                metadata_only_papers += 1
            else:
                incomplete_papers += 1

        # Display total with breakdown
        st.metric("Total Papers", total_papers)

        # Calculate percentages
        complete_pct = (complete_papers / total_papers * 100) if total_papers > 0 else 0
        metadata_pct = (metadata_only_papers / total_papers * 100) if total_papers > 0 else 0
        incomplete_pct = (incomplete_papers / total_papers * 100) if total_papers > 0 else 0

        # Compact summary text
        st.caption(
            f"{complete_papers} complete ({complete_pct:.0f}%) | "
            f"{metadata_only_papers} metadata only ({metadata_pct:.0f}%) | "
            f"{incomplete_papers} incomplete ({incomplete_pct:.0f}%)"
        )

        # Visual progress bars
        st.caption("**Data Coverage**")
        st.progress(complete_pct / 100, text=f"✅ Complete: {complete_papers}")
        st.progress(metadata_pct / 100, text=f"📋 Metadata Only: {metadata_only_papers}")
        st.progress(incomplete_pct / 100, text=f"⚠️ Incomplete: {incomplete_papers}")

        st.divider()
        st.metric("Chunks", total_chunks)

    # Main content - Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📥 Import", "Library", "🔍 Discover", "Research", "History", "Settings", "🗑️ Trash"])

