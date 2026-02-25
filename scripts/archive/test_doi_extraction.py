"""
Test DOI extraction from various publisher URLs
"""
import re
import sys

def extract_doi_from_url(url: str) -> str:
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
            else:
                return f"PII:{pii}"  # Return PII for testing

    # Cell Press PII: cell.com/joule/fulltext/S2542-4351(24)00510-5
    if 'cell.com/' in url_lower and '/fulltext/' in url_lower:
        match = re.search(r'/fulltext/([A-Z0-9()-]+)', url, re.IGNORECASE)
        if match:
            pii = match.group(1).replace('(', '').replace(')', '')
            # Try to look up DOI from PII via CrossRef
            doi = lookup_doi_from_pii(pii)
            if doi:
                return doi
            else:
                return f"PII:{pii}"  # Return PII for testing

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
    Look up DOI from PII - not reliable, return None.
    Enrichment will use Semantic Scholar title search instead.
    """
    return None


# Test cases
test_urls = [
    ("https://www.nature.com/articles/s41560-019-0356-8", "10.1038/s41560-019-0356-8", True),
    ("https://www.sciencedirect.com/science/article/pii/S2352152X24044748", "PII:S2352152X24044748", False),  # PII extraction only
    ("https://www.cell.com/joule/fulltext/S2542-4351(24)00510-5", "PII:S25424351240051O5", False),  # PII extraction only
    ("https://www.mdpi.com/2313-0105/8/10/151", "10.3390/2313-0105/8/10/151", True),
    ("https://iopscience.iop.org/article/10.1149/1945-7111/abae37", "10.1149/1945-7111/abae37", True),
    ("https://doi.org/10.1038/s41560-024-01675-8", "10.1038/s41560-024-01675-8", True),
    ("https://onlinelibrary.wiley.com/doi/full/10.1002/adma.202402024", "10.1002/adma.202402024", True),
    ("https://link.springer.com/article/10.1007/s12274-024-6447-x", "10.1007/s12274-024-6447-x", True),
]

print("Testing DOI Extraction")
print("="*100)

passed = 0
failed = 0

for url, expected, is_full_doi in test_urls:
    print(f"\nURL: {url}")
    result = extract_doi_from_url(url)

    if is_full_doi:
        # Expect full DOI extraction
        if result == expected:
            print(f"  Extracted: {result}")
            print(f"  [PASS]")
            passed += 1
        else:
            print(f"  Extracted: {result}")
            print(f"  Expected: {expected}")
            print(f"  [FAIL]")
            failed += 1
    else:
        # PII-based URLs - just check if we got the PII
        if result and result.startswith("PII:"):
            print(f"  Extracted: {result}")
            print(f"  [PASS] PII extracted (will use Semantic Scholar for DOI)")
            passed += 1
        else:
            print(f"  Extracted: {result}")
            print(f"  Expected: {expected}")
            print(f"  [FAIL] Should extract PII")
            failed += 1

print()
print("="*100)
print(f"Results: {passed} passed, {failed} failed")
print("="*100)

if failed == 0:
    print("\nAll tests passed!")
    sys.exit(0)
else:
    print(f"\n{failed} tests failed. Check the extraction logic.")
    sys.exit(1)
