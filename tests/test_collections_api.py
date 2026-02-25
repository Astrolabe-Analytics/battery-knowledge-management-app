"""
Tests for the Collections API routes (api/routes/collections.py).

Covers: CRUD operations, paper assignment, bulk operations.
"""

from unittest.mock import patch

import pytest


class TestListCollections:

    @patch("lib.db_operations.get_all_collections")
    def test_list_collections(self, mock_fn, client, sample_collection):
        mock_fn.return_value = [sample_collection]
        resp = client.get("/api/collections")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["collections"]) == 1
        assert data["collections"][0]["name"] == "Key Papers"

    @patch("lib.db_operations.get_all_collections")
    def test_list_empty(self, mock_fn, client):
        mock_fn.return_value = []
        resp = client.get("/api/collections")
        assert resp.json()["collections"] == []


class TestCreateCollection:

    @patch("lib.db_operations.create_collection")
    def test_create_success(self, mock_fn, client):
        mock_fn.return_value = {"success": True, "message": "Created", "id": 5}
        resp = client.post("/api/collections", json={
            "name": "New Collection", "color": "#ff0000", "description": "Test"
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["id"] == 5

    @patch("lib.db_operations.create_collection")
    def test_create_duplicate(self, mock_fn, client):
        mock_fn.return_value = {"success": False, "message": "Already exists"}
        resp = client.post("/api/collections", json={"name": "Existing"})
        assert resp.status_code == 400


class TestGetCollection:

    @patch("lib.db_operations.get_collection_by_id")
    def test_get_collection(self, mock_fn, client, sample_collection):
        mock_fn.return_value = sample_collection
        resp = client.get("/api/collections/1")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Key Papers"

    @patch("lib.db_operations.get_collection_by_id")
    def test_get_not_found(self, mock_fn, client):
        mock_fn.return_value = None
        resp = client.get("/api/collections/999")
        assert resp.status_code == 404


class TestUpdateCollection:

    @patch("lib.db_operations.update_collection")
    def test_update_success(self, mock_fn, client):
        mock_fn.return_value = {"success": True, "message": "Updated"}
        resp = client.patch("/api/collections/1", json={"name": "Renamed"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_update_no_fields(self, client):
        resp = client.patch("/api/collections/1", json={})
        assert resp.status_code == 400


class TestDeleteCollection:

    @patch("lib.db_operations.delete_collection")
    def test_delete_success(self, mock_fn, client):
        mock_fn.return_value = {"success": True, "message": "Deleted"}
        resp = client.delete("/api/collections/1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestPaperAssignment:

    @patch("lib.db_operations.add_paper_to_collection")
    def test_add_paper(self, mock_fn, client):
        mock_fn.return_value = {"success": True, "message": "Added"}
        resp = client.post("/api/collections/1/papers", json={"filename": "test.pdf"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("lib.db_operations.add_paper_to_collection")
    def test_add_duplicate(self, mock_fn, client):
        mock_fn.return_value = {"success": False, "message": "Already in collection"}
        resp = client.post("/api/collections/1/papers", json={"filename": "test.pdf"})
        assert resp.json()["success"] is False

    @patch("lib.db_operations.remove_paper_from_collection")
    def test_remove_paper(self, mock_fn, client):
        mock_fn.return_value = {"success": True, "message": "Removed"}
        resp = client.delete("/api/collections/1/papers/test.pdf")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestBulkPaperAssignment:

    @patch("lib.db_operations.add_paper_to_collection")
    def test_bulk_add(self, mock_fn, client):
        mock_fn.return_value = {"success": True}
        resp = client.post("/api/collections/1/papers/bulk", json={
            "filenames": ["a.pdf", "b.pdf", "c.pdf"]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["added"] == 3
        assert data["total"] == 3

    @patch("lib.db_operations.add_paper_to_collection")
    def test_bulk_add_with_duplicates(self, mock_fn, client):
        mock_fn.side_effect = [
            {"success": True}, {"success": False}, {"success": True}
        ]
        resp = client.post("/api/collections/1/papers/bulk", json={
            "filenames": ["a.pdf", "dup.pdf", "c.pdf"]
        })
        data = resp.json()
        assert data["added"] == 2
        assert data["skipped"] == 1


class TestListCollectionPapers:

    @patch("lib.db_operations.get_collection_papers")
    def test_list_papers(self, mock_fn, client):
        mock_fn.return_value = ["a.pdf", "b.pdf"]
        resp = client.get("/api/collections/1/papers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert "a.pdf" in data["filenames"]
