"""
Tests for the Import API routes (api/routes/imports.py).

Covers: URL import, DOI import, upload, metadata-only, enrichment, bulk DOI, logs.
"""

from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# URL Import
# ---------------------------------------------------------------------------

class TestURLImport:

    @patch("api.routes.imports._run_ingestion_pipeline_pg")
    @patch("api.routes.imports.requests")
    def test_import_arxiv(self, mock_requests, mock_pipeline, client, tmp_path):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"%PDF-1.4 fake"
        mock_requests.get.return_value = mock_resp

        with patch("api.routes.imports.Path", return_value=tmp_path):
            resp = client.post("/api/import/url", json={
                "url": "https://arxiv.org/abs/2301.12345"
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "arxiv" in data["filename"]

    @patch("api.routes.imports._query_crossref")
    @patch("api.routes.imports._find_open_access_pdf")
    @patch("api.routes.imports._save_metadata_only_paper_pg")
    @patch("api.routes.imports._extract_doi_from_url")
    def test_import_doi_link_metadata_only(
        self, mock_extract, mock_save, mock_oa, mock_crossref, client
    ):
        mock_extract.return_value = None  # Not from URL extraction
        mock_crossref.return_value = {
            "title": "Test Paper", "authors": ["Author"], "year": "2024",
            "journal": "Nature", "references": [],
        }
        mock_oa.return_value = None  # No OA PDF
        mock_save.return_value = "doi_10_1000_test.pdf"

        resp = client.post("/api/import/url", json={"url": "https://doi.org/10.1000/test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["metadata_only"] is True

    def test_import_invalid_url(self, client):
        resp = client.post("/api/import/url", json={"url": "https://example.com/random"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "Unrecognized" in data["error"]


# ---------------------------------------------------------------------------
# DOI Import
# ---------------------------------------------------------------------------

class TestDOIImport:

    @patch("api.routes.imports.import_from_url")
    def test_doi_delegates_to_url(self, mock_import, client):
        mock_import.return_value = {"success": True, "filename": "doi_test.pdf"}
        resp = client.post("/api/import/doi", json={"doi": "10.1000/test"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ---------------------------------------------------------------------------
# Metadata-Only Import
# ---------------------------------------------------------------------------

class TestMetadataOnlyImport:

    @patch("api.routes.imports._save_metadata_only_paper_pg")
    @patch("api.routes.imports._query_crossref")
    def test_import_metadata_only(self, mock_crossref, mock_save, client):
        mock_crossref.return_value = {
            "title": "Test Paper", "authors": [], "year": "2024",
            "journal": "Nature", "references": [],
        }
        mock_save.return_value = "doi_10_1000_test.pdf"
        resp = client.post("/api/import/metadata-only", json={"doi": "10.1000/test"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["metadata_only"] is True

    @patch("api.routes.imports._query_crossref")
    def test_metadata_only_crossref_fails(self, mock_crossref, client):
        mock_crossref.return_value = None
        resp = client.post("/api/import/metadata-only", json={"doi": "10.9999/bad"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

class TestUpload:

    @patch("api.routes.imports._run_ingestion_pipeline_pg")
    def test_upload_pdf(self, mock_pipeline, client, tmp_path):
        with patch("api.routes.imports.Path") as MockPath:
            mock_papers = tmp_path / "papers"
            mock_papers.mkdir()
            MockPath.return_value = mock_papers

            resp = client.post(
                "/api/import/upload",
                files=[("files", ("test.pdf", b"%PDF-1.4 fake", "application/pdf"))],
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_processed"] >= 0


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------

class TestEnrichment:

    @patch("lib.crossref._present")
    @patch("lib.crossref.apply_crossref_enrichment")
    @patch("lib.crossref.find_doi_via_semantic_scholar")
    @patch("lib.crossref.extract_doi_from_filename")
    @patch("lib.crossref.extract_doi_from_url")
    @patch("lib.crossref.scrape_doi_from_page")
    @patch("lib.crossref.query_crossref")
    @patch("lib.db_operations.save_paper_references")
    @patch("lib.db_operations.upsert_paper")
    @patch("lib.db_operations.get_paper_library")
    def test_enrich_no_papers_needed(
        self, mock_lib, mock_upsert, mock_refs, mock_crossref,
        mock_scrape, mock_url, mock_fname, mock_s2, mock_apply,
        mock_present, client
    ):
        mock_lib.return_value = [
            {"filename": "a.pdf", "authors": "Author", "year": "2024", "journal": "Nature"}
        ]
        mock_present.return_value = True
        resp = client.post("/api/import/enrich", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "No papers need enrichment"

    @patch("lib.crossref._present")
    @patch("lib.crossref.apply_crossref_enrichment")
    @patch("lib.crossref.find_doi_via_semantic_scholar")
    @patch("lib.crossref.extract_doi_from_filename")
    @patch("lib.crossref.extract_doi_from_url")
    @patch("lib.crossref.scrape_doi_from_page")
    @patch("lib.crossref.query_crossref")
    @patch("lib.db_operations.save_paper_references")
    @patch("lib.db_operations.upsert_paper")
    @patch("lib.db_operations.get_paper_library")
    @patch("time.sleep")
    def test_enrich_with_doi(
        self, mock_sleep, mock_lib, mock_upsert, mock_refs, mock_crossref,
        mock_scrape, mock_url, mock_fname, mock_s2, mock_apply,
        mock_present, client
    ):
        mock_lib.return_value = [
            {"filename": "a.pdf", "authors": [], "year": "", "journal": "", "doi": "10.1000/x",
             "title": "Paper", "url": "", "source_url": ""}
        ]
        mock_present.side_effect = lambda v: bool(v) and v not in ("Unknown", "unknown", "", "N/A")
        mock_crossref.return_value = {
            "title": "Paper", "authors": ["Auth"], "year": "2024",
            "journal": "J", "references": [],
        }
        mock_apply.return_value = {"authors": ["Auth"], "year": "2024", "journal": "J"}

        resp = client.post("/api/import/enrich", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["enriched"] >= 1


class TestEnrichmentStatus:

    @patch("lib.db.get_session")
    def test_enrichment_status(self, mock_session, client):
        # Create mock papers
        mock_paper1 = MagicMock()
        mock_paper1.crossref_verified = True
        mock_paper1.authors = ["Author"]
        mock_paper1.year = "2024"
        mock_paper1.journal = "Nature"
        mock_paper1.doi = "10.1000/x"
        mock_paper1.source_url = ""
        mock_paper1.title = "Complete Paper"
        mock_paper1.deleted_at = None

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.query.return_value.filter.return_value.all.return_value = [mock_paper1]
        mock_session.return_value = mock_ctx

        with patch("lib.crossref._present", side_effect=lambda v: bool(v) and str(v).strip().lower() not in ("unknown", "not specified", "none", "n/a", "")):
            resp = client.get("/api/import/enrich/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_papers" in data
        assert "needs_enrichment" in data


# ---------------------------------------------------------------------------
# Bulk DOI
# ---------------------------------------------------------------------------

class TestBulkDOI:

    @patch("api.routes.imports.import_from_url")
    def test_bulk_doi_import(self, mock_import, client):
        mock_import.return_value = {"success": True, "filename": "doi_test.pdf"}
        resp = client.post("/api/import/bulk-doi", json={"dois": ["10.1/a", "10.1/b"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["succeeded"] == 2


# ---------------------------------------------------------------------------
# Import Logs
# ---------------------------------------------------------------------------

class TestImportLogs:

    def test_logs_no_dir(self, client):
        with patch("api.routes.imports.Path") as MockPath:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = False
            MockPath.return_value = mock_dir
            resp = client.get("/api/import/logs")
        assert resp.status_code == 200
        assert resp.json()["logs"] == []


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

class TestInternalHelpers:

    def test_extract_doi_from_url(self):
        from api.routes.imports import _extract_doi_from_url
        assert _extract_doi_from_url("https://doi.org/10.1038/s41560-024-001") == "10.1038/s41560-024-001"
        assert _extract_doi_from_url("https://example.com/") is None

    def test_query_crossref_timeout(self):
        from api.routes.imports import _query_crossref
        with patch("api.routes.imports.requests.get", side_effect=Exception("timeout")):
            result = _query_crossref("10.1000/bad")
            assert result is None
