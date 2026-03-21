"""
Tests for the Discover API routes (api/routes/discover.py).

Covers: Semantic Scholar search, gap analysis, add paper.
"""

from unittest.mock import patch, MagicMock

import pytest


class TestSemanticScholarSearch:

    @patch("lib.db_operations.get_library_dois_and_titles")
    @patch("lib.semantic_scholar.check_papers_in_library")
    @patch("lib.semantic_scholar.format_paper_for_display")
    @patch("lib.semantic_scholar.search_papers")
    def test_search(self, mock_search, mock_format, mock_check, mock_dois, client):
        mock_search.return_value = {"data": [{"paperId": "abc123"}]}
        mock_format.return_value = {
            "title": "Test Paper", "authors": "Author", "year": "2024",
            "citations": 50, "doi": "10.1000/test",
        }
        mock_dois.return_value = (set(), set())
        mock_check.return_value = [{"title": "Test Paper", "in_library": False}]

        resp = client.post("/api/discover/search", json={"query": "battery EIS"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @patch("lib.semantic_scholar.search_papers")
    def test_search_empty(self, mock_search, client):
        mock_search.return_value = {"data": []}
        resp = client.post("/api/discover/search", json={"query": "xyz"})
        assert resp.json()["total"] == 0

    @patch("lib.semantic_scholar.search_papers")
    def test_search_no_data(self, mock_search, client):
        mock_search.return_value = {}
        resp = client.post("/api/discover/search", json={"query": "xyz"})
        assert resp.json()["total"] == 0


class TestGapAnalysis:

    @patch("api.routes.discover._analyze_reference_gaps_pg")
    def test_get_gaps(self, mock_gaps, client):
        mock_gaps.return_value = (
            [{"title": "Missing Paper", "citation_count": 10, "cited_by": ["paper1.pdf"]}],
            {"total_gaps": 1, "total_citations": 10, "avg_citations_per_gap": 10.0, "top_gap_count": 10},
        )
        resp = client.get("/api/discover/gaps")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stats"]["total_gaps"] == 1
        assert len(data["gaps"]) == 1

    @patch("api.routes.discover._analyze_reference_gaps_pg")
    def test_get_gaps_with_limit(self, mock_gaps, client):
        mock_gaps.return_value = ([], {"total_gaps": 0, "total_citations": 0, "avg_citations_per_gap": 0, "top_gap_count": 0})
        resp = client.get("/api/discover/gaps", params={"limit": 5})
        assert resp.status_code == 200
        mock_gaps.assert_called_once_with(limit=5)


class TestAddFromDiscover:

    @patch("lib.db_operations.add_chunks")
    @patch("lib.db_operations.save_paper_references")
    @patch("lib.db_operations.upsert_paper")
    @patch("lib.jats.strip_jats")
    @patch("api.routes.discover._query_crossref")
    @patch("sentence_transformers.SentenceTransformer")
    def test_add_paper_metadata_only(
        self, mock_st, mock_crossref, mock_jats, mock_upsert, mock_refs, mock_chunks, client
    ):
        mock_crossref.return_value = {
            "title": "Found Paper", "authors": ["Author"],
            "year": "2024", "journal": "Nature", "abstract": "",
            "volume": "", "issue": "", "pages": "",
            "author_keywords": [], "references": [],
        }
        mock_jats.return_value = ""
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=MagicMock(return_value=[0.1]*384))
        mock_st.return_value = mock_model

        resp = client.post("/api/discover/add", json={
            "doi": "10.1000/test", "title": "Found Paper",
            "authors": "Author", "year": "2024",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    @patch("lib.db_operations.add_chunks")
    @patch("lib.db_operations.save_paper_references")
    @patch("lib.db_operations.upsert_paper")
    @patch("lib.jats.strip_jats")
    @patch("api.routes.discover._query_crossref")
    @patch("sentence_transformers.SentenceTransformer")
    def test_add_paper_no_crossref(
        self, mock_st, mock_crossref, mock_jats, mock_upsert, mock_refs, mock_chunks, client
    ):
        mock_crossref.return_value = None
        mock_jats.return_value = ""
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=MagicMock(return_value=[0.1]*384))
        mock_st.return_value = mock_model

        resp = client.post("/api/discover/add", json={
            "doi": "10.1000/bad", "title": "Manual Paper",
        })
        assert resp.status_code == 200
        # Should still succeed with manual data
        assert resp.json()["success"] is True


class TestGapsAdd:

    @patch("api.routes.discover.add_from_discover")
    def test_gaps_add_delegates(self, mock_add, client):
        mock_add.return_value = {"success": True, "message": "Added"}
        resp = client.post("/api/discover/gaps/add", json={
            "doi": "10.1000/gap", "title": "Gap Paper",
        })
        assert resp.status_code == 200
        mock_add.assert_called_once()
