"""
Tests for the Papers API routes (api/routes/papers.py).

Covers: list/filter, detail, metadata update, notes, read status,
        delete/trash/restore, stats, charts, references, PDF serving.
"""

from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# List / Filter
# ---------------------------------------------------------------------------

class TestListPapers:
    """GET /api/papers — listing with filters, sort, pagination."""

    @patch("api.routes.papers._get_enriched_papers")
    def test_list_returns_papers(self, mock_enriched, client, sample_papers_list):
        mock_enriched.return_value = sample_papers_list
        resp = client.get("/api/papers")
        assert resp.status_code == 200
        data = resp.json()
        assert "papers" in data
        assert data["total"] == 3

    @patch("api.routes.papers._get_enriched_papers")
    def test_list_empty_library(self, mock_enriched, client):
        mock_enriched.return_value = []
        resp = client.get("/api/papers")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @patch("api.routes.papers._get_enriched_papers")
    def test_search_filter(self, mock_enriched, client, sample_papers_list):
        mock_enriched.return_value = sample_papers_list
        resp = client.get("/api/papers", params={"search": "degradation"})
        data = resp.json()
        assert data["total"] >= 1
        assert any("Degradation" in p["title"] for p in data["papers"])

    @patch("api.routes.papers._get_enriched_papers")
    def test_chemistry_filter(self, mock_enriched, client, sample_papers_list):
        mock_enriched.return_value = sample_papers_list
        resp = client.get("/api/papers", params={"chemistry": "LFP"})
        data = resp.json()
        for p in data["papers"]:
            assert "LFP" in p["chemistries"]

    @patch("api.routes.papers._get_enriched_papers")
    def test_topic_filter(self, mock_enriched, client, sample_papers_list):
        mock_enriched.return_value = sample_papers_list
        resp = client.get("/api/papers", params={"topic": "soh"})
        data = resp.json()
        for p in data["papers"]:
            assert "soh" in p["topics"]

    @patch("api.routes.papers._get_enriched_papers")
    def test_paper_type_filter(self, mock_enriched, client, sample_papers_list):
        mock_enriched.return_value = sample_papers_list
        resp = client.get("/api/papers", params={"paper_type": "Experimental"})
        data = resp.json()
        for p in data["papers"]:
            assert p["paper_type"] == "Experimental"

    @patch("api.routes.papers._get_enriched_papers")
    def test_status_filter(self, mock_enriched, client, sample_papers_list):
        # Enrich with status
        for p in sample_papers_list:
            p["status"] = "Incomplete"
        sample_papers_list[0]["status"] = "AI Summary"
        mock_enriched.return_value = sample_papers_list
        resp = client.get("/api/papers", params={"status": "AI Summary"})
        data = resp.json()
        assert data["total"] == 1

    @patch("api.routes.papers._get_enriched_papers")
    def test_collection_filter(self, mock_enriched, client, sample_papers_list):
        sample_papers_list[0]["collections"] = [{"name": "Key Papers", "id": 1}]
        sample_papers_list[1]["collections"] = []
        sample_papers_list[2]["collections"] = []
        mock_enriched.return_value = sample_papers_list
        resp = client.get("/api/papers", params={"collection": "Key Papers"})
        data = resp.json()
        assert data["total"] == 1

    @patch("api.routes.papers._get_enriched_papers")
    def test_pagination(self, mock_enriched, client, sample_papers_list):
        mock_enriched.return_value = sample_papers_list
        resp = client.get("/api/papers", params={"offset": 0, "limit": 2})
        data = resp.json()
        assert len(data["papers"]) == 2
        assert data["total"] == 3

    @patch("api.routes.papers._get_enriched_papers")
    def test_sort_by_title_asc(self, mock_enriched, client, sample_papers_list):
        mock_enriched.return_value = sample_papers_list
        resp = client.get("/api/papers", params={"sort": "title", "sort_dir": "asc"})
        data = resp.json()
        titles = [p["title"] for p in data["papers"]]
        assert titles == sorted(titles, key=str.lower)


# ---------------------------------------------------------------------------
# Filenames endpoint
# ---------------------------------------------------------------------------

class TestListFilenames:

    @patch("api.routes.papers._get_enriched_papers")
    def test_filenames_returns_list(self, mock_enriched, client, sample_papers_list):
        mock_enriched.return_value = sample_papers_list
        resp = client.get("/api/papers/filenames")
        data = resp.json()
        assert "filenames" in data
        assert data["total"] == 3

    @patch("api.routes.papers._get_enriched_papers")
    def test_filenames_with_search(self, mock_enriched, client, sample_papers_list):
        mock_enriched.return_value = sample_papers_list
        resp = client.get("/api/papers/filenames", params={"search": "degradation"})
        data = resp.json()
        assert data["total"] >= 1


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

class TestGetFilters:

    @patch("lib.db_operations.get_filter_options")
    def test_returns_filter_options(self, mock_fn, client):
        mock_fn.return_value = {
            "chemistries": ["LFP", "NMC"],
            "topics": ["degradation", "soh"],
            "paper_types": ["Experimental", "Review"],
        }
        resp = client.get("/api/papers/filters")
        assert resp.status_code == 200
        data = resp.json()
        assert "chemistries" in data
        assert "LFP" in data["chemistries"]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:

    @patch("lib.db_operations.get_collection_count")
    @patch("api.routes.papers._get_enriched_papers")
    def test_stats(self, mock_enriched, mock_chunks, client, sample_papers_list):
        for p in sample_papers_list:
            p["status"] = "Incomplete"
        sample_papers_list[0]["status"] = "AI Summary"
        mock_enriched.return_value = sample_papers_list
        mock_chunks.return_value = 1500
        resp = client.get("/api/papers/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_papers"] == 3
        assert data["ai_summary"] == 1
        assert data["chunk_count"] == 1500


class TestChartData:

    @patch("api.routes.papers._get_enriched_papers")
    def test_chart_data(self, mock_enriched, client, sample_papers_list):
        mock_enriched.return_value = sample_papers_list
        resp = client.get("/api/papers/stats/charts")
        assert resp.status_code == 200
        data = resp.json()
        assert "by_chemistry" in data
        assert "by_topic" in data
        assert "by_year" in data
        assert "by_type" in data
        assert "by_read_status" in data


# ---------------------------------------------------------------------------
# Paper Detail
# ---------------------------------------------------------------------------

class TestPaperDetail:

    @patch("lib.db_operations.get_paper_collections")
    @patch("lib.db_operations.get_read_status")
    @patch("lib.db_operations.get_paper_details")
    def test_get_paper(self, mock_details, mock_read, mock_colls, client, sample_paper_detail):
        mock_details.return_value = sample_paper_detail
        mock_read.return_value = {"battery_degradation_2024.pdf": False}
        mock_colls.return_value = []
        with patch("api.routes.papers.PAPERS_DIR", Path("nonexistent")):
            resp = client.get("/api/papers/battery_degradation_2024.pdf")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Lithium-Ion Battery Degradation Mechanisms"

    @patch("lib.db_operations.get_paper_details")
    def test_get_paper_not_found(self, mock_details, client):
        mock_details.return_value = None
        resp = client.get("/api/papers/nonexistent.pdf")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Metadata Update
# ---------------------------------------------------------------------------

class TestMetadataUpdate:

    @patch("api.routes.papers.invalidate_papers_cache")
    @patch("lib.db_operations.update_paper_metadata_field")
    def test_update_metadata(self, mock_update, mock_invalidate, client):
        mock_update.return_value = True
        resp = client.patch(
            "/api/papers/test.pdf/metadata",
            json={"title": "New Title", "year": "2025"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert "title" in resp.json()["updated_fields"]
        assert mock_update.call_count == 2

    @patch("lib.db_operations.update_paper_metadata_field")
    def test_update_metadata_no_fields(self, mock_update, client):
        resp = client.patch("/api/papers/test.pdf/metadata", json={})
        assert resp.status_code == 400

    @patch("lib.db_operations.update_paper_metadata_field")
    def test_update_metadata_not_found(self, mock_update, client):
        mock_update.return_value = False
        resp = client.patch("/api/papers/test.pdf/metadata", json={"title": "X"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

class TestNotes:

    @patch("lib.db_operations.update_paper_metadata_field")
    def test_update_notes(self, mock_update, client):
        mock_update.return_value = True
        resp = client.put("/api/papers/test.pdf/notes", json={"content": "My notes"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("lib.db_operations.get_paper_details")
    def test_get_notes(self, mock_details, client):
        mock_details.return_value = {"notes": "Stored notes"}
        resp = client.get("/api/papers/test.pdf/notes")
        assert resp.status_code == 200
        assert resp.json()["content"] == "Stored notes"

    @patch("lib.db_operations.get_paper_details")
    def test_get_notes_empty(self, mock_details, client):
        mock_details.return_value = {"notes": ""}
        resp = client.get("/api/papers/test.pdf/notes")
        assert resp.json()["content"] == ""


# ---------------------------------------------------------------------------
# Read Status
# ---------------------------------------------------------------------------

class TestReadStatus:

    @patch("lib.db_operations.mark_as_read")
    def test_set_read(self, mock_mark, client):
        resp = client.put("/api/papers/test.pdf/read", json={"read": True})
        assert resp.status_code == 200
        assert resp.json()["read"] is True
        mock_mark.assert_called_once_with("test.pdf")

    @patch("lib.db_operations.mark_as_unread")
    def test_set_unread(self, mock_mark, client):
        resp = client.put("/api/papers/test.pdf/read", json={"read": False})
        assert resp.status_code == 200
        assert resp.json()["read"] is False
        mock_mark.assert_called_once_with("test.pdf")

    @patch("api.routes.papers.invalidate_papers_cache")
    @patch("lib.db_operations.toggle_read_status")
    def test_toggle_read(self, mock_toggle, mock_invalidate, client):
        mock_toggle.return_value = True
        resp = client.post("/api/papers/test.pdf/read/toggle")
        assert resp.status_code == 200
        assert resp.json()["read"] is True


# ---------------------------------------------------------------------------
# Delete / Trash / Restore
# ---------------------------------------------------------------------------

class TestDelete:

    @patch("api.routes.papers.invalidate_papers_cache")
    @patch("lib.db_operations.delete_paper")
    def test_soft_delete(self, mock_del, mock_invalidate, client):
        mock_del.return_value = True
        resp = client.request("DELETE", "/api/papers", json={"filenames": ["a.pdf", "b.pdf"]})
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 2

    @patch("lib.db_operations.get_deleted_papers")
    def test_list_trash(self, mock_trash, client):
        mock_trash.return_value = [{"filename": "trashed.pdf", "deleted_at": "2024-01-01"}]
        resp = client.get("/api/papers/trash")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @patch("api.routes.papers.invalidate_papers_cache")
    @patch("lib.db_operations.restore_paper")
    def test_restore_paper(self, mock_restore, mock_invalidate, client):
        mock_restore.return_value = True
        resp = client.post("/api/papers/trash/restore", json={"filenames": ["trashed.pdf"]})
        assert resp.status_code == 200
        assert resp.json()["results"][0]["success"] is True

    @patch("api.routes.papers.invalidate_papers_cache")
    @patch("lib.db_operations.empty_trash")
    def test_empty_trash(self, mock_empty, mock_invalidate, client):
        mock_empty.return_value = 3
        resp = client.delete("/api/papers/trash")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 3

    @patch("api.routes.papers.invalidate_papers_cache")
    @patch("lib.db_operations.hard_delete_paper")
    def test_hard_delete_one(self, mock_hard, mock_invalidate, client):
        mock_hard.return_value = True
        resp = client.delete("/api/papers/trash/test.pdf")
        assert resp.status_code == 200

    @patch("lib.db_operations.hard_delete_paper")
    def test_hard_delete_not_found(self, mock_hard, client):
        mock_hard.return_value = False
        resp = client.delete("/api/papers/trash/missing.pdf")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PDF Serving
# ---------------------------------------------------------------------------

class TestServePDF:

    def test_pdf_not_found(self, client):
        with patch("api.routes.papers.PAPERS_DIR", Path("nonexistent_dir")):
            resp = client.get("/api/papers/missing.pdf/pdf")
            assert resp.status_code == 404

    def test_serve_pdf(self, client, mock_papers_dir):
        with patch("api.routes.papers.PAPERS_DIR", mock_papers_dir):
            resp = client.get("/api/papers/battery_degradation_2024.pdf/pdf")
            assert resp.status_code == 200
            assert "application/pdf" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------

class TestReferences:

    @patch("lib.db_operations.get_paper_library")
    @patch("lib.db_operations.get_paper_details")
    def test_get_references(self, mock_details, mock_library, client):
        mock_details.return_value = {
            "references": [
                {"DOI": "10.1000/ref1", "article-title": "Ref Paper One"},
                {"DOI": "", "article-title": "Ref Paper Two"},
            ]
        }
        mock_library.return_value = [
            {"doi": "10.1000/ref1", "title": "Ref Paper One", "filename": "ref1.pdf"},
        ]
        resp = client.get("/api/papers/test.pdf/references")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        # First ref should be in library (DOI match)
        assert data["references"][0]["in_library"] is True

    @patch("lib.db_operations.get_paper_details")
    def test_references_not_found(self, mock_details, client):
        mock_details.return_value = None
        resp = client.get("/api/papers/missing.pdf/references")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Enrich
# ---------------------------------------------------------------------------

class TestEnrich:

    @patch("lib.db_operations.get_paper_details")
    @patch("lib.db_operations.upsert_paper")
    @patch("lib.db_operations.save_paper_references")
    @patch("lib.crossref.query_crossref")
    @patch("lib.crossref.extract_doi_from_url")
    @patch("lib.crossref.extract_doi_from_filename")
    @patch("lib.crossref.find_doi_via_semantic_scholar")
    @patch("lib.crossref.scrape_doi_from_page")
    @patch("lib.crossref.apply_crossref_enrichment")
    @patch("lib.crossref._present")
    def test_enrich_with_existing_doi(
        self, mock_present, mock_apply, mock_scrape, mock_s2, mock_fname,
        mock_url, mock_crossref, mock_save_refs, mock_upsert, mock_details, client
    ):
        mock_details.side_effect = [
            {"doi": "10.1038/test", "title": "Test Paper", "source_url": ""},
            {"doi": "10.1038/test", "title": "Test Paper (updated)"},
        ]
        mock_crossref.return_value = {
            "title": "Test Paper", "authors": ["Smith"], "year": "2024",
            "journal": "Nature", "references": [],
        }
        mock_apply.return_value = {"title": "Test Paper"}
        mock_present.return_value = True

        resp = client.post("/api/papers/test.pdf/enrich")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    @patch("lib.db_operations.get_paper_details")
    def test_enrich_not_found(self, mock_details, client):
        mock_details.return_value = None
        resp = client.post("/api/papers/missing.pdf/enrich")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Paper status helper
# ---------------------------------------------------------------------------

class TestPaperStatusHelper:
    """Test the _get_paper_status function directly."""

    def test_ai_summary_status(self):
        from api.routes.papers import _get_paper_status
        paper = {
            "filename": "test.pdf", "title": "Real Title", "authors": "Author",
            "year": "2024", "journal": "Journal", "ai_summary": "Summary text",
        }
        with patch("api.routes.papers.PAPERS_DIR", Path("papers")):
            with patch.object(Path, "exists", return_value=True):
                assert _get_paper_status(paper) == "AI Summary"

    def test_complete_status(self):
        from api.routes.papers import _get_paper_status
        paper = {
            "filename": "test.pdf", "title": "Real Title", "authors": "Author",
            "year": "2024", "journal": "Journal",
        }
        with patch("api.routes.papers.PAPERS_DIR", Path("papers")):
            with patch.object(Path, "exists", return_value=True):
                assert _get_paper_status(paper) == "Complete"

    def test_metadata_only_status(self):
        from api.routes.papers import _get_paper_status
        paper = {
            "filename": "test.pdf", "title": "Real Title", "authors": "Author",
            "year": "2024", "journal": "Journal",
        }
        with patch("api.routes.papers.PAPERS_DIR", Path("papers")):
            with patch.object(Path, "exists", return_value=False):
                assert _get_paper_status(paper) == "Metadata Only"

    def test_incomplete_status(self):
        from api.routes.papers import _get_paper_status
        paper = {
            "filename": "test.pdf", "title": "Unknown", "authors": "",
            "year": "", "journal": "",
        }
        with patch("api.routes.papers.PAPERS_DIR", Path("papers")):
            with patch.object(Path, "exists", return_value=True):
                assert _get_paper_status(paper) == "Incomplete"
