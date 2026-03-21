"""
Citation graph endpoints — nodes and edges for the interactive graph visualization.

Builds a graph from the paper_references table by matching reference DOIs
to library papers.  Returns { nodes, edges, stats } for the frontend.
"""

from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter()


def _norm_doi(d: str) -> str:
    """Normalize a DOI for matching."""
    d = d.lower().strip()
    for pfx in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:"):
        if d.startswith(pfx):
            d = d[len(pfx):]
    return d


@router.get("/graph")
def get_citation_graph(
    filename: Optional[str] = Query(None, description="Center graph on this paper"),
    min_edges: int = Query(1, ge=1, description="Min edges to include a node"),
):
    """
    Return citation graph data: nodes (library papers) and edges (cites relationships).

    Only includes internal edges (both papers in library).
    """
    from lib.db import get_session
    from lib.models import Paper, PaperReference
    from sqlalchemy import select

    with get_session() as session:
        # Build DOI → filename lookup for all library papers
        rows = session.execute(
            select(Paper.filename, Paper.doi, Paper.title, Paper.year, Paper.authors, Paper.journal)
            .where(Paper.deleted_at.is_(None))
        ).all()

        doi_to_filename = {}
        paper_info = {}
        for fn, doi, title, year, authors, journal in rows:
            paper_info[fn] = {
                "id": fn,
                "title": title or fn,
                "year": year or "",
                "authors": (authors or [])[:3],
                "journal": journal or "",
            }
            if doi:
                doi_to_filename[_norm_doi(doi)] = fn

        # Load all references that have DOIs
        refs = session.execute(
            select(PaperReference.paper_filename, PaperReference.doi)
            .where(PaperReference.doi.isnot(None))
            .where(PaperReference.doi != "")
        ).all()

    # Build edges: source (citing paper) → target (cited paper, if in library)
    edges = []
    citing_count = {}   # filename → number of papers it cites (in library)
    cited_count = {}    # filename → number of papers that cite it (in library)

    seen_edges = set()
    for src_filename, ref_doi in refs:
        if not ref_doi:
            continue
        norm = _norm_doi(ref_doi)
        tgt_filename = doi_to_filename.get(norm)
        if not tgt_filename or tgt_filename == src_filename:
            continue
        # src_filename must also be in library (not deleted)
        if src_filename not in paper_info:
            continue

        edge_key = (src_filename, tgt_filename)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)

        edges.append({"source": src_filename, "target": tgt_filename})
        citing_count[src_filename] = citing_count.get(src_filename, 0) + 1
        cited_count[tgt_filename] = cited_count.get(tgt_filename, 0) + 1

    # Determine which nodes to include
    all_connected = set()
    for e in edges:
        all_connected.add(e["source"])
        all_connected.add(e["target"])

    # Filter by min_edges
    def node_edge_count(fn):
        return citing_count.get(fn, 0) + cited_count.get(fn, 0)

    if filename:
        # Ego graph: show the selected paper and its neighbors
        ego_neighbors = set()
        ego_neighbors.add(filename)
        filtered_edges = []
        for e in edges:
            if e["source"] == filename or e["target"] == filename:
                ego_neighbors.add(e["source"])
                ego_neighbors.add(e["target"])
                filtered_edges.append(e)
        # Also include edges between neighbors
        for e in edges:
            if e["source"] in ego_neighbors and e["target"] in ego_neighbors:
                if e not in filtered_edges:
                    filtered_edges.append(e)
        edges = filtered_edges
        included = ego_neighbors
    else:
        # Full graph: filter to nodes with enough connections
        included = {fn for fn in all_connected if node_edge_count(fn) >= min_edges}
        edges = [e for e in edges if e["source"] in included and e["target"] in included]

    # Build node list with citation counts
    nodes = []
    for fn in included:
        if fn not in paper_info:
            continue
        node = {**paper_info[fn]}
        node["citing"] = citing_count.get(fn, 0)
        node["cited_by"] = cited_count.get(fn, 0)
        nodes.append(node)

    # Sort nodes by total connections descending
    nodes.sort(key=lambda n: n["citing"] + n["cited_by"], reverse=True)

    # Top cited papers for the stats panel
    top_cited = sorted(
        [{"filename": fn, "title": paper_info[fn]["title"], "count": cnt}
         for fn, cnt in cited_count.items() if fn in paper_info],
        key=lambda x: x["count"],
        reverse=True,
    )[:20]

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_library_papers": len(paper_info),
            "papers_with_connections": len(all_connected),
            "total_internal_edges": len(seen_edges),
            "displayed_nodes": len(nodes),
            "displayed_edges": len(edges),
        },
        "top_cited": top_cited,
    }
