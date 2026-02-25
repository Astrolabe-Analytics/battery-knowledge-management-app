"""Tests for lib/gap_analysis.py — title/DOI normalization and fuzzy matching."""

from lib.gap_analysis import normalize_doi, normalize_title, titles_match


class TestNormalizeDoi:
    """Tests for normalize_doi()."""

    def test_https_doi_org_prefix(self):
        assert normalize_doi("https://doi.org/10.1234/TEST") == "10.1234/test"

    def test_http_doi_org_prefix(self):
        assert normalize_doi("http://doi.org/10.1234/test") == "10.1234/test"

    def test_doi_org_no_protocol(self):
        assert normalize_doi("doi.org/10.1234/test") == "10.1234/test"

    def test_doi_colon_prefix(self):
        assert normalize_doi("doi:10.1234/test") == "10.1234/test"

    def test_already_clean(self):
        assert normalize_doi("10.1234/test") == "10.1234/test"

    def test_uppercase_lowered(self):
        assert normalize_doi("10.1234/TEST.Paper") == "10.1234/test.paper"

    def test_empty_string(self):
        assert normalize_doi("") == ""

    def test_none_input(self):
        assert normalize_doi(None) == ""

    def test_whitespace_stripped(self):
        assert normalize_doi("  10.1234/test  ") == "10.1234/test"

    def test_real_doi_nature(self):
        assert normalize_doi("https://doi.org/10.1038/s41560-023-01234-5") == "10.1038/s41560-023-01234-5"

    def test_real_doi_elsevier(self):
        assert normalize_doi("https://doi.org/10.1016/j.jpowsour.2023.233456") == "10.1016/j.jpowsour.2023.233456"


class TestNormalizeTitle:
    """Tests for normalize_title()."""

    def test_basic_normalization(self):
        assert normalize_title("  A  Battery   Paper  ") == "a battery paper"

    def test_lowercase(self):
        assert normalize_title("State of Health Estimation") == "state of health estimation"

    def test_multiple_spaces(self):
        assert normalize_title("word1   word2     word3") == "word1 word2 word3"

    def test_tabs_and_newlines(self):
        assert normalize_title("word1\tword2\nword3") == "word1 word2 word3"

    def test_empty_string(self):
        assert normalize_title("") == ""

    def test_none_input(self):
        assert normalize_title(None) == ""

    def test_already_normalized(self):
        assert normalize_title("simple title") == "simple title"

    def test_leading_trailing_whitespace(self):
        assert normalize_title("   hello   ") == "hello"


class TestTitlesMatch:
    """Tests for titles_match()."""

    def test_exact_match(self):
        assert titles_match(
            "State of Health Estimation",
            "State of Health Estimation",
        ) is True

    def test_case_insensitive_match(self):
        assert titles_match(
            "State of Health Estimation",
            "state of health estimation",
        ) is True

    def test_whitespace_insensitive_match(self):
        assert titles_match(
            "State  of  Health  Estimation",
            "State of Health Estimation",
        ) is True

    def test_very_different_titles(self):
        assert titles_match(
            "State of Health Estimation for Batteries",
            "Completely Different Topic About Chemistry",
        ) is False

    def test_empty_first_title(self):
        assert titles_match("", "Some Title") is False

    def test_empty_second_title(self):
        assert titles_match("Some Title", "") is False

    def test_both_empty(self):
        assert titles_match("", "") is False

    def test_none_first(self):
        assert titles_match(None, "Some Title") is False

    def test_none_second(self):
        assert titles_match("Some Title", None) is False

    def test_fuzzy_match_minor_difference(self):
        # Titles that are very similar but not identical
        assert titles_match(
            "State of Health Estimation for Lithium-Ion Batteries",
            "State of Health Estimation for Lithium Ion Batteries",
        ) is True

    def test_fuzzy_match_below_threshold(self):
        assert titles_match(
            "State of Health Estimation",
            "State of Charge Prediction",
        ) is False

    def test_custom_threshold_loose(self):
        assert titles_match(
            "Battery Health Monitoring",
            "Battery Health Analysis",
            threshold=0.7,
        ) is True

    def test_custom_threshold_strict(self):
        assert titles_match(
            "Battery Health Monitoring System",
            "Battery Health Monitoring Systems",
            threshold=0.99,
        ) is False
