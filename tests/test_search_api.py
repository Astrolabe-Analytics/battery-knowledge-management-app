"""
Tests for the Search API routes (api/routes/search.py).

Covers: chunk search, RAG ask pipeline (with mocked LLM + embeddings).
"""

from unittest.mock import patch, MagicMock

import pytest


class TestChunkSearch:

    @patch("lib.db_operations.retrieve_relevant_chunks")
    def test_search_chunks(self, mock_search, client):
        mock_search.return_value = [
            {
                "text": "Battery degradation occurs...",
                "filename": "paper.pdf",
                "page_num": 1,
                "chunk_index": 0,
                "section_name": "Introduction",
                "score": 0.92,
            }
        ]
        resp = client.post("/api/search/chunks", json={"query": "battery degradation"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["chunks"][0]["score"] == 0.92

    @patch("lib.db_operations.retrieve_relevant_chunks")
    def test_search_with_filters(self, mock_search, client):
        mock_search.return_value = []
        resp = client.post("/api/search/chunks", json={
            "query": "EIS",
            "top_k": 3,
            "chemistry": "LFP",
            "topic": "soh",
        })
        assert resp.status_code == 200
        mock_search.assert_called_once_with(
            question="EIS",
            top_k=3,
            filter_chemistry="LFP",
            filter_topic="soh",
            filter_paper_type=None,
        )

    @patch("lib.db_operations.retrieve_relevant_chunks")
    def test_search_empty_results(self, mock_search, client):
        mock_search.return_value = []
        resp = client.post("/api/search/chunks", json={"query": "nonexistent topic"})
        assert resp.json()["total"] == 0


class TestRAGAsk:

    @patch("lib.db_operations.save_query")
    @patch("lib.llm.query_claude")
    @patch("lib.llm.rerank_chunks")
    @patch("lib.llm.expand_query")
    @patch("lib.llm.get_api_key_from_env")
    @patch("lib.db_operations.hybrid_search")
    def test_ask_full_pipeline(
        self, mock_hybrid, mock_key, mock_expand, mock_rerank, mock_claude, mock_save, client
    ):
        mock_key.return_value = "sk-test-key"
        mock_expand.return_value = "expanded battery degradation query"
        mock_hybrid.return_value = [
            {"text": "Chunk 1", "filename": "a.pdf", "hybrid_score": 0.9},
            {"text": "Chunk 2", "filename": "b.pdf", "hybrid_score": 0.8},
        ]
        mock_rerank.return_value = [
            {"text": "Chunk 1", "filename": "a.pdf", "hybrid_score": 0.9},
        ]
        mock_claude.return_value = "Based on the evidence, battery degradation..."
        mock_save.return_value = 42

        resp = client.post("/api/search/ask", json={
            "question": "What causes battery degradation?",
            "top_k": 1,
            "n_candidates": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "degradation" in data["answer"]
        assert data["query_id"] == 42

    @patch("lib.llm.get_api_key_from_env")
    def test_ask_no_api_key(self, mock_key, client):
        mock_key.return_value = None
        resp = client.post("/api/search/ask", json={"question": "test?"})
        assert resp.status_code == 500

    @patch("lib.db_operations.save_query")
    @patch("lib.llm.query_claude")
    @patch("lib.llm.expand_query")
    @patch("lib.llm.get_api_key_from_env")
    @patch("lib.db_operations.hybrid_search")
    def test_ask_no_results(
        self, mock_hybrid, mock_key, mock_expand, mock_claude, mock_save, client
    ):
        mock_key.return_value = "sk-test"
        mock_expand.return_value = "query"
        mock_hybrid.return_value = []

        resp = client.post("/api/search/ask", json={"question": "obscure topic?"})
        assert resp.status_code == 200
        assert "No relevant" in resp.json()["answer"]

    @patch("lib.db_operations.save_query")
    @patch("lib.llm.query_claude")
    @patch("lib.llm.expand_query")
    @patch("lib.llm.get_api_key_from_env")
    @patch("lib.db_operations.hybrid_search")
    def test_ask_with_expansion_disabled(
        self, mock_hybrid, mock_key, mock_expand, mock_claude, mock_save, client
    ):
        mock_key.return_value = "sk-test"
        mock_hybrid.return_value = [{"text": "chunk", "filename": "a.pdf"}]
        mock_claude.return_value = "Answer"
        mock_save.return_value = 1

        resp = client.post("/api/search/ask", json={
            "question": "direct question",
            "enable_query_expansion": False,
            "enable_reranking": False,
        })
        assert resp.status_code == 200
        mock_expand.assert_not_called()

    @patch("lib.db_operations.save_query")
    @patch("lib.llm.query_claude")
    @patch("lib.llm.expand_query")
    @patch("lib.llm.get_api_key_from_env")
    @patch("lib.db_operations.hybrid_search")
    @patch("lib.db_operations.get_collection_papers")
    def test_ask_with_collection_filter(
        self, mock_coll, mock_hybrid, mock_key, mock_expand, mock_claude, mock_save, client
    ):
        mock_key.return_value = "sk-test"
        mock_expand.return_value = "query"
        mock_coll.return_value = ["paper1.pdf", "paper2.pdf"]
        mock_hybrid.return_value = [{"text": "chunk", "filename": "paper1.pdf"}]
        mock_claude.return_value = "Answer"
        mock_save.return_value = 1

        resp = client.post("/api/search/ask", json={
            "question": "test?",
            "collection_id": 5,
        })
        assert resp.status_code == 200
        mock_coll.assert_called_once_with(5)
