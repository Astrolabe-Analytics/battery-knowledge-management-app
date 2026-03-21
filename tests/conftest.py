"""
Shared test fixtures for Astrolabe API tests.

All tests mock lib.db_operations functions so no real database is needed.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """FastAPI TestClient with papers cache invalidated between tests."""
    from api.main import app
    from api.routes.papers import invalidate_papers_cache

    invalidate_papers_cache()
    with TestClient(app) as c:
        yield c
    invalidate_papers_cache()


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_paper_dict():
    """A single realistic paper dict as returned by get_paper_library()."""
    return {
        "filename": "battery_degradation_2024.pdf",
        "title": "Lithium-Ion Battery Degradation Mechanisms",
        "authors": "Smith, J.; Jones, A.",
        "year": "2024",
        "journal": "Nature Energy",
        "doi": "10.1038/s41560-024-00001-1",
        "source_url": "",
        "crossref_verified": True,
        "author_keywords": ["lithium-ion", "degradation"],
        "chemistries": ["LFP", "NMC"],
        "topics": ["degradation", "soh"],
        "application": "electric vehicles",
        "paper_type": "Experimental",
        "num_pages": 12,
        "date_added": "2024-06-15T10:30:00+00:00",
        "pdf_status": "complete",
        "feed_blurb": "LFP cells show 20% less degradation than NMC under fast charging.",
        "ai_summary": "## Overview\nThis paper examines degradation...",
    }


@pytest.fixture()
def sample_papers_list(sample_paper_dict):
    """A list of 3 papers with varying completeness levels."""
    complete = sample_paper_dict.copy()

    metadata_only = {
        "filename": "doi_10_1016_j_jpowsour_2023_001.pdf",
        "title": "SOH Estimation Using EIS",
        "authors": "Wang, X.; Chen, Y.",
        "year": "2023",
        "journal": "Journal of Power Sources",
        "doi": "10.1016/j.jpowsour.2023.001",
        "source_url": "",
        "crossref_verified": True,
        "author_keywords": [],
        "chemistries": ["NMC"],
        "topics": ["soh", "eis"],
        "application": "general",
        "paper_type": "Experimental",
        "num_pages": 0,
        "date_added": "2024-07-01T00:00:00+00:00",
        "pdf_status": "metadata_only",
        "feed_blurb": "",
        "ai_summary": "",
    }

    incomplete = {
        "filename": "url_12345.pdf",
        "title": "Unknown",
        "authors": "",
        "year": "",
        "journal": "",
        "doi": "",
        "source_url": "",
        "crossref_verified": False,
        "author_keywords": [],
        "chemistries": [],
        "topics": [],
        "application": "general",
        "paper_type": "Experimental",
        "num_pages": 5,
        "date_added": "2024-05-01T00:00:00+00:00",
        "pdf_status": "",
        "feed_blurb": "",
        "ai_summary": "",
    }

    return [complete, metadata_only, incomplete]


@pytest.fixture()
def sample_paper_detail():
    """Detailed paper dict as returned by get_paper_details()."""
    return {
        "filename": "battery_degradation_2024.pdf",
        "title": "Lithium-Ion Battery Degradation Mechanisms",
        "authors": ["Smith, J.", "Jones, A."],
        "year": "2024",
        "journal": "Nature Energy",
        "doi": "10.1038/s41560-024-00001-1",
        "source_url": "",
        "crossref_verified": True,
        "author_keywords": ["lithium-ion", "degradation"],
        "chemistries": ["LFP", "NMC"],
        "topics": ["degradation", "soh"],
        "application": "electric vehicles",
        "paper_type": "Experimental",
        "num_pages": 12,
        "date_added": "2024-06-15T10:30:00+00:00",
        "pdf_status": "complete",
        "feed_blurb": "",
        "ai_summary": "",
        "abstract": "We study degradation in LFP and NMC cells...",
        "volume": "9",
        "issue": "3",
        "pages": "245-260",
        "notes": "",
        "metadata_only": False,
        "references": [
            {"key": "ref1", "DOI": "10.1000/ref1", "article-title": "Prior Work"},
        ],
        "preview_chunks": [
            {"page": 1, "text": "Introduction to battery degradation..."},
        ],
    }


@pytest.fixture()
def sample_collection():
    """A collection dict as returned by get_all_collections()."""
    return {
        "id": 1,
        "name": "Key Papers",
        "color": "#3b82f6",
        "description": "Important papers for the review",
        "created_date": "2024-06-01T00:00:00+00:00",
        "modified_date": "2024-06-15T00:00:00+00:00",
        "paper_count": 5,
    }


@pytest.fixture()
def sample_query():
    """A query history dict as returned by get_all_queries()."""
    return {
        "id": 1,
        "timestamp": "2024-06-15T10:30:00+00:00",
        "question": "What causes capacity fade in NMC cells?",
        "answer": "Capacity fade in NMC cells is primarily caused by...",
        "chunks": [
            {"text": "NMC degradation involves...", "filename": "paper.pdf", "score": 0.92}
        ],
        "filters": {"chemistry": "NMC"},
        "is_starred": False,
    }


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_papers_dir(tmp_path):
    """Create a temporary papers directory with a fake PDF."""
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    fake_pdf = papers_dir / "battery_degradation_2024.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake content")
    return papers_dir
