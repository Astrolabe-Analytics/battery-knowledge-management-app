"""
Tests for the History API routes (api/routes/history.py).

Covers: list queries, get single, toggle star, delete, clear all.
"""

from unittest.mock import patch

import pytest


class TestListQueries:

    @patch("lib.db_operations.get_all_queries")
    def test_list_queries(self, mock_fn, client, sample_query):
        mock_fn.return_value = [sample_query]
        resp = client.get("/api/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["queries"][0]["question"] == "What causes capacity fade in NMC cells?"

    @patch("lib.db_operations.get_all_queries")
    def test_list_with_limit(self, mock_fn, client, sample_query):
        mock_fn.return_value = [sample_query]
        resp = client.get("/api/history", params={"limit": 10})
        assert resp.status_code == 200
        mock_fn.assert_called_once_with(limit=10)

    @patch("lib.db_operations.get_starred_queries")
    def test_list_starred_only(self, mock_fn, client, sample_query):
        starred = sample_query.copy()
        starred["is_starred"] = True
        mock_fn.return_value = [starred]
        resp = client.get("/api/history", params={"starred_only": True})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @patch("lib.db_operations.get_all_queries")
    def test_list_empty(self, mock_fn, client):
        mock_fn.return_value = []
        resp = client.get("/api/history")
        assert resp.json()["total"] == 0


class TestGetQuery:

    @patch("lib.db_operations.get_query_by_id")
    def test_get_query(self, mock_fn, client, sample_query):
        mock_fn.return_value = sample_query
        resp = client.get("/api/history/1")
        assert resp.status_code == 200
        assert resp.json()["question"] == "What causes capacity fade in NMC cells?"

    @patch("lib.db_operations.get_query_by_id")
    def test_get_not_found(self, mock_fn, client):
        mock_fn.return_value = None
        resp = client.get("/api/history/999")
        assert resp.status_code == 404


class TestToggleStar:

    @patch("lib.db_operations.toggle_star")
    def test_toggle_star(self, mock_fn, client):
        mock_fn.return_value = True
        resp = client.post("/api/history/1/star")
        assert resp.status_code == 200
        assert resp.json()["starred"] is True

    @patch("lib.db_operations.toggle_star")
    def test_toggle_unstar(self, mock_fn, client):
        mock_fn.return_value = False
        resp = client.post("/api/history/1/star")
        assert resp.json()["starred"] is False


class TestDeleteQuery:

    @patch("lib.db_operations.delete_query")
    def test_delete_query(self, mock_fn, client):
        mock_fn.return_value = True
        resp = client.delete("/api/history/1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("lib.db_operations.delete_query")
    def test_delete_not_found(self, mock_fn, client):
        mock_fn.return_value = False
        resp = client.delete("/api/history/999")
        assert resp.status_code == 404


class TestClearHistory:

    @patch("lib.db_operations.clear_all_history")
    def test_clear_all(self, mock_fn, client):
        mock_fn.return_value = 10
        resp = client.delete("/api/history")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["deleted_count"] == 10
