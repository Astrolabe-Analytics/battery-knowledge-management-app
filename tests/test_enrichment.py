"""Tests for lib/enrichment.py — DOI extraction from publisher URLs."""

import pytest

from lib.enrichment import extract_doi_from_url, lookup_doi_from_pii


class TestExtractDoiFromUrl:
    """Tests for extract_doi_from_url()."""

    # --- doi.org direct URLs ---
    def test_doi_org_https(self):
        assert extract_doi_from_url("https://doi.org/10.1016/j.jpowsour.2023.001") == "10.1016/j.jpowsour.2023.001"

    def test_doi_org_http(self):
        assert extract_doi_from_url("http://doi.org/10.1016/j.jpowsour.2023.001") == "10.1016/j.jpowsour.2023.001"

    def test_doi_org_with_query_params(self):
        result = extract_doi_from_url("https://doi.org/10.1016/j.jpowsour.2023.001?ref=pdf")
        assert result == "10.1016/j.jpowsour.2023.001"

    def test_doi_org_trailing_period(self):
        result = extract_doi_from_url("https://doi.org/10.1016/j.jpowsour.2023.001.")
        assert result == "10.1016/j.jpowsour.2023.001"

    def test_doi_org_trailing_comma(self):
        result = extract_doi_from_url("https://doi.org/10.1016/j.jpowsour.2023.001,")
        assert result == "10.1016/j.jpowsour.2023.001"

    def test_doi_org_trailing_semicolon(self):
        result = extract_doi_from_url("https://doi.org/10.1016/j.jpowsour.2023.001;")
        assert result == "10.1016/j.jpowsour.2023.001"

    def test_doi_org_trailing_paren(self):
        result = extract_doi_from_url("https://doi.org/10.1016/j.jpowsour.2023.001)")
        assert result == "10.1016/j.jpowsour.2023.001"

    # --- Nature ---
    def test_nature_article(self):
        result = extract_doi_from_url("https://www.nature.com/articles/s41560-023-01234-5")
        assert result == "10.1038/s41560-023-01234-5"

    def test_nature_article_with_query(self):
        result = extract_doi_from_url("https://www.nature.com/articles/s41560-023-01234-5?utm_source=twitter")
        assert result == "10.1038/s41560-023-01234-5"

    # --- MDPI ---
    def test_mdpi_article(self):
        result = extract_doi_from_url("https://www.mdpi.com/2313-0105/9/3/123")
        assert result == "10.3390/2313-0105/9/3/123"

    # --- IOP Science ---
    def test_iop_article(self):
        result = extract_doi_from_url("https://iopscience.iop.org/article/10.1088/1945-7111/ac6c2f")
        assert result == "10.1088/1945-7111/ac6c2f"

    def test_iop_article_long_doi_falls_back_to_generic(self):
        # BUG: IOP regex only captures 2 path segments after registrant.
        # DOIs with 3+ segments (e.g., 10.1088/1742-6596/1234/1/012345)
        # will be truncated by the IOP-specific regex. The generic fallback
        # then picks up but also truncates. This is a known limitation.
        result = extract_doi_from_url("https://iopscience.iop.org/article/10.1088/1742-6596/1234/1/012345")
        # Current behavior: truncated — captures "10.1088/1742-6596/1234" (2 segments)
        assert result == "10.1088/1742-6596/1234"

    # --- ScienceDirect (PII — returns None since PII lookup is a stub) ---
    def test_sciencedirect_pii(self):
        result = extract_doi_from_url("https://www.sciencedirect.com/science/article/pii/S0378775323001234")
        assert result is None

    # --- Cell Press (PII — returns None) ---
    def test_cell_press_pii(self):
        result = extract_doi_from_url("https://www.cell.com/joule/fulltext/S2542-4351(23)00123-4")
        assert result is None

    # --- Wiley ---
    def test_wiley_full(self):
        result = extract_doi_from_url("https://onlinelibrary.wiley.com/doi/full/10.1002/aenm.202301234")
        assert result == "10.1002/aenm.202301234"

    def test_wiley_abs(self):
        result = extract_doi_from_url("https://onlinelibrary.wiley.com/doi/abs/10.1002/aenm.202301234")
        assert result == "10.1002/aenm.202301234"

    def test_wiley_direct_doi(self):
        result = extract_doi_from_url("https://onlinelibrary.wiley.com/doi/10.1002/aenm.202301234")
        assert result == "10.1002/aenm.202301234"

    # --- Springer ---
    def test_springer_article(self):
        result = extract_doi_from_url("https://link.springer.com/article/10.1007/s10853-023-08123-4")
        assert result == "10.1007/s10853-023-08123-4"

    # --- Generic DOI pattern ---
    def test_generic_doi_in_url(self):
        result = extract_doi_from_url("https://example.com/paper?doi=10.1234/test.2023.001")
        assert result == "10.1234/test.2023.001"

    def test_generic_doi_in_path(self):
        result = extract_doi_from_url("https://example.com/10.1234/test.2023.001")
        assert result == "10.1234/test.2023.001"

    # --- No DOI ---
    def test_no_doi_in_url(self):
        assert extract_doi_from_url("https://example.com/some-page") is None

    def test_no_doi_plain_text(self):
        assert extract_doi_from_url("https://www.google.com") is None

    # --- Edge cases ---
    def test_empty_string(self):
        assert extract_doi_from_url("") is None

    def test_none_input(self):
        assert extract_doi_from_url(None) is None

    def test_doi_with_hash_fragment(self):
        result = extract_doi_from_url("https://doi.org/10.1016/j.jpowsour.2023.001#section-3")
        assert result == "10.1016/j.jpowsour.2023.001"

    # --- Real-world DOI formats ---
    def test_real_elsevier_doi(self):
        result = extract_doi_from_url("https://doi.org/10.1016/j.est.2023.109456")
        assert result == "10.1016/j.est.2023.109456"

    def test_real_acs_doi(self):
        result = extract_doi_from_url("https://doi.org/10.1021/acsenergylett.3c00456")
        assert result == "10.1021/acsenergylett.3c00456"

    def test_real_rsc_doi(self):
        result = extract_doi_from_url("https://doi.org/10.1039/D3EE01234A")
        assert result == "10.1039/D3EE01234A"


class TestLookupDoiFromPii:
    """Tests for lookup_doi_from_pii() — currently a stub that returns None."""

    def test_returns_none(self):
        assert lookup_doi_from_pii("S0378775323001234") is None

    def test_returns_none_for_any_input(self):
        assert lookup_doi_from_pii("anything") is None

    def test_returns_none_for_empty(self):
        assert lookup_doi_from_pii("") is None
