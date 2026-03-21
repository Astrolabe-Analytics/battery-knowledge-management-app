import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import ForceGraph2D from 'react-force-graph-2d';
import { GitBranch, Award, ArrowUpRight, ArrowDownLeft, RotateCcw } from 'lucide-react';
import { fetchCitationGraph } from '../services/api';
import styles from './CitationGraph.module.css';

const NODE_COLORS = {
  focused: '#2563eb',    // blue — selected paper
  highCited: '#7c3aed',  // purple — highly cited
  normal: '#64748b',     // slate — default
};

export default function CitationGraph() {
  const navigate = useNavigate();
  const graphRef = useRef();
  const containerRef = useRef();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [focusedPaper, setFocusedPaper] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [minEdges, setMinEdges] = useState(5);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // Fetch citation graph
  const loadGraph = useCallback((filename, edges) => {
    setLoading(true);
    fetchCitationGraph(filename, edges)
      .then(d => {
        setData(d);
        // Convert to force-graph format
        const nodes = d.nodes.map(n => ({
          id: n.id,
          title: n.title,
          year: n.year,
          authors: n.authors,
          journal: n.journal,
          citing: n.citing,
          cited_by: n.cited_by,
          total: n.citing + n.cited_by,
        }));
        const links = d.edges.map(e => ({
          source: e.source,
          target: e.target,
        }));
        setGraphData({ nodes, links });
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadGraph(focusedPaper, minEdges);
  }, [focusedPaper, minEdges, loadGraph]);

  // Resize observer for graph container
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Node appearance
  const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const total = node.total || 0;
    const r = Math.max(3, Math.min(12, 3 + total * 0.5));

    // Color based on role
    let color = NODE_COLORS.normal;
    if (node.id === focusedPaper) color = NODE_COLORS.focused;
    else if (node.cited_by >= 5) color = NODE_COLORS.highCited;

    // Draw circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();

    // Label for large enough nodes or when zoomed in
    if (globalScale > 1.5 || total >= 5) {
      const label = (node.title || '').slice(0, 40) + (node.title?.length > 40 ? '...' : '');
      const fontSize = Math.max(8, 10 / globalScale);
      ctx.font = `${fontSize}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillStyle = 'var(--astro-text, #334155)';
      ctx.fillText(label, node.x, node.y + r + 2);
    }
  }, [focusedPaper]);

  const nodePointerAreaPaint = useCallback((node, color, ctx) => {
    const total = node.total || 0;
    const r = Math.max(3, Math.min(12, 3 + total * 0.5)) + 3;
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
  }, []);

  const handleNodeClick = useCallback((node) => {
    setSelectedNode(node);
  }, []);

  const handleNodeDoubleClick = useCallback((node) => {
    setFocusedPaper(node.id);
    setSelectedNode(null);
  }, []);

  function handleReset() {
    setFocusedPaper(null);
    setSelectedNode(null);
  }

  function handleTopCitedClick(filename) {
    setFocusedPaper(filename);
    setSelectedNode(null);
  }

  if (loading && !data) {
    return <div className={styles.loading}>Loading citation graph...</div>;
  }

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <h1 className={styles.title}><GitBranch size={24} /> Citation Graph</h1>
          <span className={styles.subtitle}>
            {focusedPaper
              ? `Showing connections for: ${data?.nodes?.find(n => n.id === focusedPaper)?.title?.slice(0, 50) || focusedPaper}`
              : 'Internal citation network across your library'}
          </span>
        </div>
        <div className={styles.controls}>
          {!focusedPaper && (
            <>
              <span className={styles.controlLabel}>Min connections:</span>
              <select
                className={styles.controlSelect}
                value={minEdges}
                onChange={e => setMinEdges(Number(e.target.value))}
              >
                <option value={1}>1+</option>
                <option value={2}>2+</option>
                <option value={3}>3+</option>
                <option value={5}>5+</option>
                <option value={10}>10+</option>
              </select>
            </>
          )}
          {focusedPaper && (
            <button className={styles.resetBtn} onClick={handleReset}>
              <RotateCcw size={12} /> Show full graph
            </button>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <span className={styles.legendDot} style={{ background: NODE_COLORS.focused }} /> Selected
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendDot} style={{ background: NODE_COLORS.highCited }} /> Highly cited (5+)
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendDot} style={{ background: NODE_COLORS.normal }} /> Other
        </span>
        <span>Click = details | Double-click = focus | Scroll = zoom</span>
      </div>

      {/* Body: graph + sidebar */}
      <div className={styles.body}>
        <div className={styles.graphContainer} ref={containerRef}>
          {graphData.nodes.length > 0 ? (
            <ForceGraph2D
              ref={graphRef}
              width={dimensions.width}
              height={dimensions.height}
              graphData={graphData}
              nodeCanvasObject={nodeCanvasObject}
              nodePointerAreaPaint={nodePointerAreaPaint}
              onNodeClick={handleNodeClick}
              onNodeDblClick={handleNodeDoubleClick}
              linkColor={() => 'rgba(100, 116, 139, 0.15)'}
              linkDirectionalArrowLength={3}
              linkDirectionalArrowRelPos={1}
              linkWidth={0.5}
              d3AlphaDecay={0.05}
              d3VelocityDecay={0.3}
              cooldownTicks={100}
              enableNodeDrag={true}
            />
          ) : (
            <div className={styles.loading}>
              {loading ? 'Loading...' : 'No citation connections found.'}
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className={styles.sidebar}>
          {/* Stats */}
          {data?.stats && (
            <div className={styles.statGrid}>
              <div className={styles.statCard}>
                <div className={styles.statValue}>{data.stats.displayed_nodes}</div>
                <div className={styles.statLabel}>Papers shown</div>
              </div>
              <div className={styles.statCard}>
                <div className={styles.statValue}>{data.stats.displayed_edges}</div>
                <div className={styles.statLabel}>Citation links</div>
              </div>
              <div className={styles.statCard}>
                <div className={styles.statValue}>{data.stats.total_internal_edges}</div>
                <div className={styles.statLabel}>Total internal</div>
              </div>
              <div className={styles.statCard}>
                <div className={styles.statValue}>{data.stats.papers_with_connections}</div>
                <div className={styles.statLabel}>Connected papers</div>
              </div>
            </div>
          )}

          {/* Selected paper detail */}
          {selectedNode && (
            <div className={styles.paperDetail}>
              <div
                className={styles.paperDetailTitle}
                onClick={() => navigate(`/paper/${encodeURIComponent(selectedNode.id)}`)}
              >
                {selectedNode.title}
              </div>
              <div className={styles.paperDetailMeta}>
                {selectedNode.authors?.join(', ')}
                {selectedNode.year && ` (${selectedNode.year})`}
                {selectedNode.journal && <><br />{selectedNode.journal}</>}
              </div>
              <div className={styles.paperDetailStats}>
                <span className={styles.paperDetailStat}>
                  <ArrowUpRight size={12} /> Cites {selectedNode.citing} papers
                </span>
                <span className={styles.paperDetailStat}>
                  <ArrowDownLeft size={12} /> Cited by {selectedNode.cited_by}
                </span>
              </div>
            </div>
          )}

          {/* Top cited papers */}
          {data?.top_cited?.length > 0 && (
            <div className={styles.topCitedSection}>
              <div className={styles.topCitedTitle}>
                <Award size={14} /> Most Cited in Library
              </div>
              {data.top_cited.slice(0, 15).map((p, i) => (
                <div
                  key={p.filename}
                  className={styles.topCitedItem}
                  onClick={() => handleTopCitedClick(p.filename)}
                >
                  <span className={styles.citedRank}>{i + 1}</span>
                  <span className={styles.citedTitle}>
                    {p.title?.slice(0, 60)}{p.title?.length > 60 ? '...' : ''}
                  </span>
                  <span className={styles.citedCount}>{p.count}x</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
