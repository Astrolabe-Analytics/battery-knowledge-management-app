"""Tests for the citations API routes (citation graph)."""

from unittest.mock import patch, MagicMock


def test_citation_graph_full(client):
    """GET /api/citations/graph returns nodes and edges."""
    mock_session = MagicMock()

    # Mock library papers
    papers_data = [
        ("paper_a.pdf", "10.1000/a", "Paper A", "2023", ["Author 1"], "Journal A"),
        ("paper_b.pdf", "10.1000/b", "Paper B", "2022", ["Author 2"], "Journal B"),
        ("paper_c.pdf", "10.1000/c", "Paper C", "2021", ["Author 3"], "Journal C"),
    ]
    mock_session.execute.return_value.all.side_effect = [
        papers_data,
        # References: A cites B, A cites C, B cites C
        [
            ("paper_a.pdf", "10.1000/b"),
            ("paper_a.pdf", "10.1000/c"),
            ("paper_b.pdf", "10.1000/c"),
        ],
    ]

    with patch("lib.db.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/citations/graph?min_edges=1")
        assert resp.status_code == 200
        data = resp.json()

        assert "nodes" in data
        assert "edges" in data
        assert "stats" in data
        assert "top_cited" in data
        assert data["stats"]["total_internal_edges"] == 3
        assert len(data["nodes"]) == 3
        assert len(data["edges"]) == 3


def test_citation_graph_ego(client):
    """GET /api/citations/graph?filename=... returns ego graph."""
    mock_session = MagicMock()

    papers_data = [
        ("paper_a.pdf", "10.1000/a", "Paper A", "2023", ["Author 1"], "Journal A"),
        ("paper_b.pdf", "10.1000/b", "Paper B", "2022", ["Author 2"], "Journal B"),
        ("paper_c.pdf", "10.1000/c", "Paper C", "2021", ["Author 3"], "Journal C"),
        ("paper_d.pdf", "10.1000/d", "Paper D", "2020", ["Author 4"], "Journal D"),
    ]

    # A cites B and C; D cites C (D not connected to A)
    refs_data = [
        ("paper_a.pdf", "10.1000/b"),
        ("paper_a.pdf", "10.1000/c"),
        ("paper_d.pdf", "10.1000/c"),
    ]

    mock_session.execute.return_value.all.side_effect = [papers_data, refs_data]

    with patch("lib.db.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/citations/graph?filename=paper_a.pdf")
        assert resp.status_code == 200
        data = resp.json()

        # Ego graph for A: should include A, B, C (neighbors of A)
        # D is connected to C but not directly to A
        node_ids = {n["id"] for n in data["nodes"]}
        assert "paper_a.pdf" in node_ids
        assert "paper_b.pdf" in node_ids
        assert "paper_c.pdf" in node_ids
        # D is NOT a neighbor of A
        assert "paper_d.pdf" not in node_ids


def test_citation_graph_min_edges_filter(client):
    """min_edges parameter filters low-connection nodes."""
    mock_session = MagicMock()

    papers_data = [
        ("paper_a.pdf", "10.1000/a", "Paper A", "2023", [], ""),
        ("paper_b.pdf", "10.1000/b", "Paper B", "2022", [], ""),
        ("paper_c.pdf", "10.1000/c", "Paper C", "2021", [], ""),
    ]

    # A cites B and C; B only has 1 connection from A
    refs_data = [
        ("paper_a.pdf", "10.1000/b"),
        ("paper_a.pdf", "10.1000/c"),
        ("paper_c.pdf", "10.1000/a"),
    ]

    mock_session.execute.return_value.all.side_effect = [papers_data, refs_data]

    with patch("lib.db.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        # With min_edges=2: B (only 1 edge) gets filtered out
        resp = client.get("/api/citations/graph?min_edges=2")
        assert resp.status_code == 200
        data = resp.json()

        node_ids = {n["id"] for n in data["nodes"]}
        # A has 3 edges (cites B, cites C, cited by C), C has 2 edges (cited by A, cites A)
        assert "paper_a.pdf" in node_ids
        assert "paper_c.pdf" in node_ids
        # B only has 1 edge, filtered out
        assert "paper_b.pdf" not in node_ids


def test_citation_graph_empty(client):
    """Graph with no references returns empty results."""
    mock_session = MagicMock()

    papers_data = [
        ("paper_a.pdf", "10.1000/a", "Paper A", "2023", [], ""),
    ]

    mock_session.execute.return_value.all.side_effect = [papers_data, []]

    with patch("lib.db.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/citations/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 0
        assert len(data["edges"]) == 0
        assert data["stats"]["total_internal_edges"] == 0


def test_citation_graph_doi_normalization(client):
    """DOIs with different prefixes are correctly matched."""
    mock_session = MagicMock()

    papers_data = [
        ("paper_a.pdf", "https://doi.org/10.1000/a", "Paper A", "2023", [], ""),
        ("paper_b.pdf", "10.1000/b", "Paper B", "2022", [], ""),
    ]

    # Reference has doi.org prefix
    refs_data = [
        ("paper_a.pdf", "doi:10.1000/b"),
    ]

    mock_session.execute.return_value.all.side_effect = [papers_data, refs_data]

    with patch("lib.db.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        resp = client.get("/api/citations/graph?min_edges=1")
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["edges"]) == 1
        assert data["edges"][0]["source"] == "paper_a.pdf"
        assert data["edges"][0]["target"] == "paper_b.pdf"
