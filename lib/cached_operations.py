"""
Cached expensive operations for performance.
Uses @st.cache_data to avoid recomputing on every rerun.
"""
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import json
from typing import List, Dict, Any


@st.cache_data(ttl=60)  # Cache for 60 seconds
def build_library_dataframe(papers: List[Dict], search_query: str, filter_chemistry: str,
                            filter_topic: str, filter_paper_type: str,
                            filter_collection: str, filter_status: str) -> pd.DataFrame:
    """
    Build the library table DataFrame with formatting.
    Cached to avoid rebuilding on every interaction.

    Args:
        papers: List of paper dicts
        search_query: Text search query (searches title, authors, journal, DOI, keywords, tags)
        filter_chemistry: Chemistry filter value
        filter_topic: Topic filter value
        filter_paper_type: Paper type filter value
        filter_collection: Collection filter value
        filter_status: Status filter value

    Returns:
        Formatted DataFrame ready for AG Grid
    """
    from lib import read_status, collections
    from lib.app_helpers import clean_html_from_text

    # Apply filters
    filtered_papers = papers

    # Text search filter
    if search_query:
        search_lower = search_query.lower()
        filtered_papers = [
            p for p in filtered_papers
            if (search_lower in p.get('title', '').lower() or
                search_lower in p.get('authors', '').lower() or
                search_lower in p.get('journal', '').lower() or
                search_lower in p.get('doi', '').lower() or
                any(search_lower in kw.lower() for kw in p.get('author_keywords', [])) or
                any(search_lower in chem.lower() for chem in p.get('chemistries', [])) or
                any(search_lower in topic.lower() for topic in p.get('topics', [])))
        ]

    if filter_chemistry != "All Chemistries":
        filtered_papers = [
            p for p in filtered_papers
            if filter_chemistry in p.get('chemistries', [])
        ]

    if filter_topic != "All Topics":
        filtered_papers = [
            p for p in filtered_papers
            if filter_topic in p.get('topics', [])
        ]

    if filter_paper_type != "All Types":
        filtered_papers = [
            p for p in filtered_papers
            if p.get('paper_type') == filter_paper_type.lower()
        ]

    if filter_collection != "All Collections":
        from lib import collections as collections_db
        all_collections = collections_db.get_all_collections()
        selected_collection = next((c for c in all_collections if c['name'] == filter_collection), None)
        if selected_collection:
            collection_filenames = set(collections_db.get_collection_papers(selected_collection['id']))
            filtered_papers = [p for p in filtered_papers if p.get('filename') in collection_filenames]

    if filter_status != "All Papers":
        filtered_papers = [
            p for p in filtered_papers
            if get_paper_status(p) == filter_status
        ]

    # Get read statuses
    filenames = [p['filename'] for p in filtered_papers]
    read_statuses = read_status.get_read_status(filenames)

    # Build DataFrame
    df_data = []
    for paper in filtered_papers:
        # Format authors
        authors_list = paper.get('authors', '').split(';') if paper.get('authors') else []
        authors_display = '; '.join([a.strip() for a in authors_list[:3] if a.strip()])
        if len(authors_list) > 3:
            authors_display += '; et al.'

        # Format DOI
        doi = paper.get('doi', '')
        doi_clean, doi_url = format_doi(doi)
        doi_display = doi_clean if doi_clean else '—'

        # Clean HTML from title
        title = paper.get('title', paper['filename'].replace('.pdf', ''))
        title = clean_html_from_text(title)

        # Format date
        date_added_str = format_date(paper.get('date_added', ''))

        # Determine status
        status = get_paper_status(paper)

        # Get collections
        paper_collections = collections.get_paper_collections(paper['filename'])
        collections_str = ', '.join([c['name'] for c in paper_collections]) if paper_collections else ''

        df_data.append({
            'Select': '',
            'Status': status,
            'Title': title,
            'Authors': authors_display,
            'Year': paper.get('year', ''),
            'Journal': paper.get('journal', ''),
            'Collections': collections_str,
            'Added': date_added_str,
            'DOI': doi_display,
            'Read': read_statuses.get(paper['filename'], False),
            '_filename': paper['filename'],
            '_doi_url': doi_url,
            '_paper_title': title
        })

    return pd.DataFrame(df_data)


def get_paper_status(paper: Dict) -> str:
    """Determine paper status based on pdf_status field or metadata and PDF existence.

    Status definitions:
    - Summarized: has complete metadata + PDF + fully processed + AI summary
    - Complete: has complete metadata + PDF + fully processed (embedded)
    - Metadata Only: has complete metadata but no PDF
    - Incomplete: missing critical metadata fields or processing incomplete
    - Processing Pending: has complete metadata + PDF but not yet processed

    Note: Prefers pdf_status field from metadata.json (set by mark_incomplete_metadata.py).
    Falls back to calculating from metadata if pdf_status not available.
    """
    # Use pdf_status field if available (set by mark_incomplete_metadata.py)
    pdf_status = paper.get('pdf_status', '').lower()

    if pdf_status == 'summarized':
        return "🤖 Summarized"
    elif pdf_status == 'complete':
        return "✅ Complete"
    elif pdf_status == 'metadata_only':
        return "📋 Metadata Only"
    elif pdf_status == 'incomplete':
        return "⚠️ Incomplete"
    elif pdf_status == 'processing_pending':
        return "🔄 Processing Pending"

    # Fallback to old calculation logic if pdf_status not set
    has_title = bool(paper.get('title', '').strip())
    has_authors = bool(paper.get('authors') and paper.get('authors') != [])
    has_year = bool(paper.get('year', '').strip())
    has_journal = bool(paper.get('journal', '').strip())
    has_doi = bool(paper.get('doi', '').strip())  # DOI is now required
    metadata_complete = has_title and has_authors and has_year and has_journal and has_doi

    pdf_path = Path("papers") / paper['filename']
    has_pdf = pdf_path.exists()

    if metadata_complete and has_pdf:
        return "✅ Complete"
    elif metadata_complete and not has_pdf:
        return "📋 Metadata Only"
    else:
        return "⚠️ Incomplete"


def format_doi(doi: str) -> tuple:
    """Format DOI for display and URL."""
    doi_clean = ''
    doi_url = ''

    if doi:
        if doi.startswith('https://doi.org/'):
            doi_url = doi
            doi_clean = doi[16:]
        elif doi.startswith('http://doi.org/'):
            doi_url = doi.replace('http://', 'https://')
            doi_clean = doi[15:]
        elif doi.startswith('10.'):
            doi_clean = doi
            doi_url = f"https://doi.org/{doi}"
        else:
            doi_clean = doi
            doi_url = doi

    return doi_clean, doi_url


def format_date(date_str: str) -> str:
    """Format date string for display."""
    if not date_str:
        return ''

    try:
        formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.split('.')[0] if '.' in date_str else date_str, fmt)
                return dt.strftime("%b %d, %Y")
            except:
                continue
        return date_str.split()[0] if date_str else ''
    except:
        return ''


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_metadata_json() -> Dict:
    """Load metadata.json with caching."""
    metadata_file = Path('data/metadata.json')
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


@st.cache_data(ttl=60)
def build_references_dataframe(references: List[Dict]) -> pd.DataFrame:
    """Build references DataFrame with formatting (cached)."""
    refs_data = []
    for idx, ref in enumerate(references):
        refs_data.append({
            '#': idx + 1,
            'Title': ref.get('title', 'Unknown'),
            'Authors': ref.get('authors', 'Unknown'),
            'Year': ref.get('year', ''),
            'DOI': ref.get('doi', ''),
            '_in_library': ref.get('in_library', False),
            '_ref_index': idx
        })
    return pd.DataFrame(refs_data)
