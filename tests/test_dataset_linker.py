"""Tests for lib/dataset_linker.py — paper ↔ dataset cross-referencing."""

import pytest

from lib.dataset_linker import (
    extract_linkable_doi,
    load_catalog_from_string,
    match_dataset_to_papers,
    cross_reference,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def paper_library():
    """A small paper library for testing matching."""
    return {
        "paper_001.pdf": {
            "title": "State of Health Estimation Using Machine Learning",
            "doi": "10.1016/j.jpowsour.2023.233456",
            "source_url": "https://www.sciencedirect.com/science/article/pii/S0378775323001234",
        },
        "paper_002.pdf": {
            "title": "Capacity Fade in NMC811 Cathodes Under Fast Charging",
            "doi": "10.1038/s41560-023-01234-5",
            "source_url": "https://www.nature.com/articles/s41560-023-01234-5",
        },
        "paper_003.pdf": {
            "title": "Review of Battery Management Systems for Electric Vehicles",
            "doi": "",
            "source_url": "",
        },
    }


@pytest.fixture
def sample_catalog_csv():
    """A minimal catalog CSV string."""
    return (
        "title,primary_data_url,primary_data_doi,data_repository,repo_record_id,"
        "paper_url,doi_structure,chemistry,cell_manufacturer,cell_model,"
        "cell_format,num_tested,test_level,data_type,dataset_type,year,"
        "authors,journal,citation,tags,code_url,notes\n"
        "SOH Dataset,https://zenodo.org/record/123,,zenodo,123,"
        "https://doi.org/10.1016/j.jpowsour.2023.233456,separate,NMC,,,"
        "cylindrical,10,cell,cycle_aging,primary,2023,,J Power Sources,,,,\n"
        "NMC Cycling Data,https://zenodo.org/record/456,,zenodo,456,"
        "https://www.nature.com/articles/s41560-023-01234-5,separate,NMC811,,,"
        ",20,cell,cycle_aging,primary,2023,,Nature Energy,,,,\n"
        "Unrelated Dataset,https://zenodo.org/record/789,,zenodo,789,"
        ",separate,LFP,,,,5,cell,eis,primary,2022,,,,,,\n"
    )


# ---------------------------------------------------------------------------
# Tests: extract_linkable_doi
# ---------------------------------------------------------------------------

class TestExtractLinkableDoi:

    def test_from_primary_data_doi(self):
        dataset = {"primary_data_doi": "10.5281/zenodo.5569522", "paper_url": ""}
        assert extract_linkable_doi(dataset) == "10.5281/zenodo.5569522"

    def test_from_paper_url_doi_org(self):
        dataset = {
            "primary_data_doi": "",
            "paper_url": "https://doi.org/10.1016/j.jpowsour.2023.233456",
        }
        assert extract_linkable_doi(dataset) == "10.1016/j.jpowsour.2023.233456"

    def test_from_paper_url_nature(self):
        dataset = {
            "primary_data_doi": "",
            "paper_url": "https://www.nature.com/articles/s41560-023-01234-5",
        }
        assert extract_linkable_doi(dataset) == "10.1038/s41560-023-01234-5"

    def test_primary_doi_takes_precedence(self):
        dataset = {
            "primary_data_doi": "10.5281/zenodo.123",
            "paper_url": "https://doi.org/10.1016/j.jpowsour.2023.001",
        }
        # primary_data_doi wins
        assert extract_linkable_doi(dataset) == "10.5281/zenodo.123"

    def test_no_doi_available(self):
        dataset = {"primary_data_doi": "", "paper_url": ""}
        assert extract_linkable_doi(dataset) is None

    def test_missing_fields(self):
        assert extract_linkable_doi({}) is None

    def test_url_without_doi(self):
        dataset = {"primary_data_doi": "", "paper_url": "https://example.com/some-page"}
        assert extract_linkable_doi(dataset) is None


# ---------------------------------------------------------------------------
# Tests: load_catalog_from_string
# ---------------------------------------------------------------------------

class TestLoadCatalogFromString:

    def test_parses_csv(self, sample_catalog_csv):
        catalog = load_catalog_from_string(sample_catalog_csv)
        assert len(catalog) == 3
        assert catalog[0]["title"] == "SOH Dataset"
        assert catalog[1]["chemistry"] == "NMC811"
        assert catalog[2]["data_repository"] == "zenodo"

    def test_all_columns_present(self, sample_catalog_csv):
        catalog = load_catalog_from_string(sample_catalog_csv)
        expected_cols = {"title", "primary_data_url", "primary_data_doi",
                         "data_repository", "paper_url", "chemistry"}
        assert expected_cols.issubset(set(catalog[0].keys()))

    def test_empty_csv(self):
        csv = "title,paper_url\n"
        catalog = load_catalog_from_string(csv)
        assert catalog == []


# ---------------------------------------------------------------------------
# Tests: match_dataset_to_papers
# ---------------------------------------------------------------------------

class TestMatchDatasetToPapers:

    def test_doi_match(self, paper_library):
        dataset = {
            "title": "Some Dataset",
            "primary_data_doi": "",
            "paper_url": "https://doi.org/10.1016/j.jpowsour.2023.233456",
        }
        matches = match_dataset_to_papers(dataset, paper_library)
        assert len(matches) == 1
        assert matches[0]["filename"] == "paper_001.pdf"
        assert matches[0]["match_type"] == "doi"
        assert matches[0]["confidence"] == "high"

    def test_url_match(self, paper_library):
        dataset = {
            "title": "Some Dataset",
            "primary_data_doi": "",
            "paper_url": "https://www.nature.com/articles/s41560-023-01234-5",
        }
        matches = match_dataset_to_papers(dataset, paper_library)
        assert len(matches) >= 1
        # Should match via DOI extracted from Nature URL or URL match
        filenames = [m["filename"] for m in matches]
        assert "paper_002.pdf" in filenames

    def test_title_match(self, paper_library):
        dataset = {
            "title": "Review of Battery Management Systems for Electric Vehicles",
            "primary_data_doi": "",
            "paper_url": "",
        }
        matches = match_dataset_to_papers(dataset, paper_library)
        assert len(matches) == 1
        assert matches[0]["filename"] == "paper_003.pdf"
        assert matches[0]["match_type"] == "title"
        assert matches[0]["confidence"] == "medium"

    def test_no_match(self, paper_library):
        dataset = {
            "title": "Completely Unrelated Oceanography Study",
            "primary_data_doi": "",
            "paper_url": "",
        }
        matches = match_dataset_to_papers(dataset, paper_library)
        assert matches == []

    def test_empty_dataset(self, paper_library):
        matches = match_dataset_to_papers({}, paper_library)
        assert matches == []

    def test_empty_library(self):
        dataset = {
            "title": "Some Dataset",
            "primary_data_doi": "10.1234/test",
            "paper_url": "",
        }
        matches = match_dataset_to_papers(dataset, {})
        assert matches == []

    def test_no_duplicate_matches(self, paper_library):
        # If DOI and URL both match the same paper, it should appear once
        dataset = {
            "title": "Something",
            "primary_data_doi": "",
            "paper_url": "https://doi.org/10.1038/s41560-023-01234-5",
        }
        matches = match_dataset_to_papers(dataset, paper_library)
        filenames = [m["filename"] for m in matches]
        assert len(filenames) == len(set(filenames))


# ---------------------------------------------------------------------------
# Tests: cross_reference (batch)
# ---------------------------------------------------------------------------

class TestCrossReference:

    def test_full_batch(self, sample_catalog_csv, paper_library):
        catalog = load_catalog_from_string(sample_catalog_csv)
        result = cross_reference(catalog, paper_library)

        assert result["stats"]["total_datasets"] == 3
        assert result["stats"]["matched"] >= 2  # First two should match
        assert result["stats"]["unmatched"] <= 1  # Third has no matching paper

    def test_stats_by_match_type(self, sample_catalog_csv, paper_library):
        catalog = load_catalog_from_string(sample_catalog_csv)
        result = cross_reference(catalog, paper_library)
        stats = result["stats"]["by_match_type"]
        assert stats["doi"] + stats["url"] + stats["title"] == result["stats"]["matched"]

    def test_empty_catalog(self, paper_library):
        result = cross_reference([], paper_library)
        assert result["stats"]["total_datasets"] == 0
        assert result["stats"]["matched"] == 0
        assert result["matches"] == []

    def test_empty_library(self, sample_catalog_csv):
        catalog = load_catalog_from_string(sample_catalog_csv)
        result = cross_reference(catalog, {})
        assert result["stats"]["matched"] == 0
        assert result["stats"]["unmatched"] == 3

    def test_match_entries_have_correct_shape(self, sample_catalog_csv, paper_library):
        catalog = load_catalog_from_string(sample_catalog_csv)
        result = cross_reference(catalog, paper_library)
        for entry in result["matches"]:
            assert "dataset_index" in entry
            assert "dataset_title" in entry
            assert "paper_matches" in entry
            assert isinstance(entry["paper_matches"], list)
