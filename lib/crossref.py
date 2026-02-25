"""
Shared CrossRef, DOI extraction, and Unpaywall utilities.

Consolidates CrossRef query logic previously duplicated across:
  - api/routes/imports.py
  - api/routes/discover.py
  - lib/_legacy/enrichment.py
"""

import re
import logging
import requests
from typing import Optional

from lib.jats import strip_jats
from lib.journal_normalizer import normalize_journal_name

logger = logging.getLogger(__name__)

# Polite CrossRef headers (https://github.com/CrossRef/rest-api-doc#etiquette)
_CROSSREF_HEADERS = {
    'User-Agent': 'AstrolabeLibrary/2.0 (mailto:researcher@example.com)',
}
_UNPAYWALL_EMAIL = 'researcher@example.com'


# ── DOI Extraction ────────────────────────────────────────────────────────


def extract_doi_from_url(url: str) -> Optional[str]:
    """
    Extract a DOI from a publisher URL.

    Handles: doi.org, Nature, MDPI, IOP, ScienceDirect, Wiley, Springer,
    ACS, RSC, IEEE, Elsevier, Taylor & Francis, and generic 10.xxxx patterns.
    """
    if not url:
        return None

    url_lower = url.lower()

    # Direct DOI URLs (doi.org/..., /doi/abs/..., /doi/full/...)
    m = re.search(r'(?:doi\.org/|/doi/(?:abs/|full/)?)(10\.\d{4,}/[^\s?&#]+)', url, re.I)
    if m:
        return m.group(1).rstrip('.,;)')

    # Nature  nature.com/articles/s41467-019-09792-9
    if 'nature.com/articles/' in url_lower:
        m = re.search(r'nature\.com/articles/([^/?#]+)', url, re.I)
        if m:
            return f"10.1038/{m.group(1).rstrip('.,;)')}"

    # MDPI  mdpi.com/2313-0105/10/7/226
    # Don't extract from URL — MDPI URL paths use ISSNs, not real DOIs.
    # The actual DOI (e.g., 10.3390/batteries7040088) must come from
    # scraping the page's meta tags.

    # IOP Science  iopscience.iop.org/article/10.xxxx/...
    if 'iopscience.iop.org/' in url_lower:
        m = re.search(r'iopscience\.iop\.org/article/(10\.\d{4,}/[\w./-]+)', url, re.I)
        if m:
            return m.group(1).rstrip('.,;)')

    # Wiley  onlinelibrary.wiley.com/doi/full/10.xxxx/...
    if 'wiley.com/doi/' in url_lower:
        m = re.search(r'wiley\.com/doi/(?:full/|abs/)?(10\.\d{4,}/[^/?#]+)', url, re.I)
        if m:
            return m.group(1).rstrip('.,;)')

    # Springer / SpringerLink  link.springer.com/article/10.xxxx/...
    if 'springer.com/' in url_lower:
        m = re.search(r'springer\.com/(?:article|chapter)/(10\.\d{4,}/[^/?#]+)', url, re.I)
        if m:
            return m.group(1).rstrip('.,;)')

    # ACS  pubs.acs.org/doi/10.xxxx/...
    if 'acs.org/doi/' in url_lower:
        m = re.search(r'acs\.org/doi/(?:abs/|full/)?(10\.\d{4,}/[^/?#]+)', url, re.I)
        if m:
            return m.group(1).rstrip('.,;)')

    # RSC  pubs.rsc.org/en/content/articlelanding/...
    if 'rsc.org/' in url_lower:
        m = re.search(r'(10\.\d{4,}/[a-zA-Z0-9]+)', url)
        if m:
            return m.group(1)

    # IEEE Xplore — DOIs are often in the page, not the URL, but try
    if 'ieeexplore.ieee.org/' in url_lower:
        m = re.search(r'document/(\d+)', url)
        # Can't construct DOI from document ID reliably
        pass

    # ScienceDirect PII-based URLs — DOI extraction requires API/scraping
    # We handle this via scraping fallback

    # Generic fallback: any 10.xxxx/... pattern in the URL
    m = re.search(r'(10\.\d{4,}/[^\s?#&]+)', url)
    if m:
        doi = m.group(1).rstrip('.,;)')
        # Strip common URL suffixes that aren't part of the DOI
        doi = re.sub(r'/(?:full|abstract|summary|pdf|suppl|meta)$', '', doi)
        # Reject ISSN-format patterns (e.g., 10.3390/2313-0105/...)
        if re.match(r'^10\.\d{4,}/\d{4}-\d{4}/', doi):
            return None
        return doi if '/' in doi else None

    return None


def extract_doi_from_filename(filename: str) -> Optional[str]:
    """
    Extract a DOI from a paper filename.

    Handles patterns like:
      - doi_10_1016_j_jpowsour_2024_235188.pdf
      - 10_1016_j_jpowsour_2024_235188.pdf
    """
    if not filename:
        return None
    # Strip .pdf extension
    name = re.sub(r'\.pdf$', '', filename, flags=re.I)
    # Remove leading "doi_"
    name = re.sub(r'^doi_', '', name, flags=re.I)
    # Check if it looks like a DOI (starts with 10_)
    if name.startswith('10_'):
        # Convert first underscore after prefix to /
        # e.g. 10_1016_j_xxx -> 10.1016/j.xxx
        parts = name.split('_', 2)
        if len(parts) >= 2:
            prefix = parts[0] + '.' + parts[1]
            suffix = '_'.join(parts[2:]) if len(parts) > 2 else ''
            doi = prefix + '/' + suffix.replace('_', '.')
            # Quick validation: DOI should be 10.xxxx/something
            if re.match(r'^10\.\d{4,}/.+', doi):
                # Reject ISSN-format patterns (e.g., 10.3390/2313-0105.7.4.88)
                if re.match(r'^10\.\d{4,}/\d{4}-\d{4}', doi):
                    return None
                return doi
    return None


# ── CrossRef Query ────────────────────────────────────────────────────────


def query_crossref(doi: str, include_references: bool = True) -> Optional[dict]:
    """
    Query CrossRef for paper metadata by DOI.

    Returns a dict with keys: title, authors, year, journal, abstract,
    volume, issue, pages, author_keywords, references.
    Returns None on failure.
    """
    if not doi:
        return None
    try:
        url = f"https://api.crossref.org/works/{doi}"
        resp = requests.get(url, headers=_CROSSREF_HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.debug(f"CrossRef returned {resp.status_code} for {doi}")
            return None

        message = resp.json().get('message', {})
        metadata = {}

        # Title
        titles = message.get('title', [])
        if titles:
            title = titles[0]
            # Clean up JATS in title
            title = strip_jats(title)
            # Remove stray HTML
            title = re.sub(r'<[^>]+>', '', title).strip()
            metadata['title'] = title

        # Authors (format: "Family, Given")
        authors = []
        for a in message.get('author', []):
            given = a.get('given', '')
            family = a.get('family', '')
            if family:
                authors.append(f"{family}, {given}" if given else family)
        metadata['authors'] = authors[:10]

        # Year
        published = message.get('published-print') or message.get('published-online')
        if published and 'date-parts' in published:
            parts = published['date-parts'][0]
            if parts and parts[0]:
                metadata['year'] = str(parts[0])

        # Journal (normalized)
        container = message.get('container-title', [])
        if container:
            metadata['journal'] = normalize_journal_name(container[0])
        else:
            metadata['journal'] = ''

        # Abstract (JATS-stripped)
        raw_abstract = message.get('abstract', '')
        if raw_abstract:
            metadata['abstract'] = strip_jats(raw_abstract)
        else:
            metadata['abstract'] = ''

        # Volume, Issue, Pages
        metadata['volume'] = message.get('volume', '')
        metadata['issue'] = message.get('issue', '')
        metadata['pages'] = message.get('page', '')

        # Keywords
        metadata['author_keywords'] = message.get('keywords', [])

        # References
        if include_references:
            refs = []
            for ref in message.get('reference', [])[:200]:
                refs.append({
                    'key': ref.get('key', ''),
                    'DOI': ref.get('DOI', ''),
                    'doi': ref.get('DOI', ''),
                    'doi-asserted-by': ref.get('doi-asserted-by', ''),
                    'article-title': ref.get('article-title', ''),
                    'title': ref.get('article-title', ref.get('unstructured', '')),
                    'author': ref.get('author', ''),
                    'year': ref.get('year', ''),
                    'journal-title': ref.get('journal-title', ''),
                    'volume': ref.get('volume', ''),
                    'first-page': ref.get('first-page', ''),
                })
            metadata['references'] = refs
        else:
            metadata['references'] = []

        return metadata

    except requests.exceptions.Timeout:
        logger.warning(f"CrossRef timeout for {doi}")
        return None
    except Exception as e:
        logger.error(f"CrossRef error for {doi}: {e}")
        return None


# ── Unpaywall Open Access PDF ─────────────────────────────────────────────


def find_open_access_pdf(doi: str) -> Optional[str]:
    """Check Unpaywall for an open-access PDF URL."""
    if not doi:
        return None
    try:
        url = f"https://api.unpaywall.org/v2/{doi}?email={_UNPAYWALL_EMAIL}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('is_oa') and data.get('best_oa_location'):
                return data['best_oa_location'].get('url_for_pdf')
    except Exception:
        pass
    return None


# ── Semantic Scholar DOI Discovery ────────────────────────────────────────


def find_doi_via_semantic_scholar(title: str) -> Optional[str]:
    """
    Search Semantic Scholar by title to find a DOI.

    Uses fuzzy title matching against top 5 results.
    Returns DOI string or None.
    """
    if not title or len(title.strip()) < 10:
        return None
    try:
        from lib.semantic_scholar import search_papers
        result = search_papers(title, limit=5, fields=['title', 'externalIds'])

        if not result.get('success') or not result.get('data'):
            return None

        title_norm = _normalize_for_matching(title)

        for paper in result['data']:
            paper_title = paper.get('title', '')
            if not paper_title:
                continue
            paper_norm = _normalize_for_matching(paper_title)

            # Check for close match
            if title_norm == paper_norm:
                doi = _extract_doi_from_s2(paper)
                if doi:
                    return doi
            # Substring match (one contains the other)
            elif title_norm in paper_norm or paper_norm in title_norm:
                doi = _extract_doi_from_s2(paper)
                if doi:
                    return doi

        return None
    except Exception as e:
        logger.debug(f"S2 DOI lookup failed for '{title[:50]}': {e}")
        return None


def _normalize_for_matching(title: str) -> str:
    """Normalize title for fuzzy matching."""
    return re.sub(r'[^\w\s]', '', title.lower()).strip()


def _extract_doi_from_s2(paper: dict) -> Optional[str]:
    """Extract DOI from Semantic Scholar paper data."""
    ext_ids = paper.get('externalIds', {})
    if ext_ids and ext_ids.get('DOI'):
        return ext_ids['DOI']
    return None


# ── Scrape DOI from publisher page ────────────────────────────────────────


def scrape_doi_from_page(url: str) -> Optional[str]:
    """
    Scrape a publisher page to find DOI in meta tags or JSON-LD.
    Used as a fallback when DOI can't be extracted from the URL itself.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    try:
        resp = requests.get(url, timeout=15, headers=headers)
        if resp.status_code != 200:
            return None

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Check meta tags
        for attr, val in [
            ('name', 'citation_doi'), ('name', 'DC.Identifier'),
            ('property', 'citation_doi'), ('name', 'DOI'),
            ('name', 'dc.identifier'), ('name', 'prism.doi'),
        ]:
            tag = soup.find('meta', {attr: val})
            if tag and tag.get('content'):
                content = tag['content'].strip()
                if 'doi.org/' in content:
                    return content.split('doi.org/')[-1]
                if content.startswith('10.'):
                    return content

        # Check JSON-LD
        for script in soup.find_all('script', {'type': 'application/ld+json'}):
            m = re.search(r'"doi"\s*:\s*"(10\.\d+/[^"]+)"', script.string or '')
            if m:
                return m.group(1)

        # Last resort: find DOI pattern in raw HTML
        m = re.search(r'\b(10\.\d{4,}/[^\s<>"\']+)\b', resp.text)
        if m:
            candidate = re.sub(r'[,;.\)]+$', '', m.group(1))
            # Clean common URL artifacts
            candidate = re.sub(r'[&?].*$', '', candidate)
            candidate = candidate.rstrip('/')
            if candidate and '/' in candidate:
                return candidate
    except Exception:
        pass
    return None


# ── Enrichment helpers ────────────────────────────────────────────────────


def _present(val) -> bool:
    """Check if a metadata value is meaningfully present."""
    if val is None:
        return False
    if isinstance(val, list):
        return len(val) > 0
    s = str(val).strip().lower()
    return s not in {'', 'unknown', 'not specified', 'none', 'n/a'}


def compute_missing_fields(paper_dict: dict) -> list[str]:
    """
    Return a list of metadata fields that are missing/empty for a paper.

    Checks: title, authors, year, journal, abstract, volume, issue, pages, doi
    """
    fields_to_check = ['title', 'authors', 'year', 'journal', 'abstract',
                        'volume', 'issue', 'pages', 'doi']
    missing = []
    for f in fields_to_check:
        if not _present(paper_dict.get(f)):
            missing.append(f)
    return missing


def apply_crossref_enrichment(paper_dict: dict, crossref_data: dict) -> dict:
    """
    Apply CrossRef metadata to fill only missing fields in a paper.

    Returns dict of {field: new_value} for fields that were updated.
    Does NOT overwrite existing present values.
    """
    updates = {}

    field_map = {
        'title': 'title',
        'authors': 'authors',
        'year': 'year',
        'journal': 'journal',
        'abstract': 'abstract',
        'volume': 'volume',
        'issue': 'issue',
        'pages': 'pages',
        'author_keywords': 'author_keywords',
    }

    for paper_field, crossref_field in field_map.items():
        if not _present(paper_dict.get(paper_field)):
            cr_val = crossref_data.get(crossref_field)
            if _present(cr_val):
                updates[paper_field] = cr_val

    return updates
