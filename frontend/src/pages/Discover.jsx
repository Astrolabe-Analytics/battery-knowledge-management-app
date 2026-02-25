import { useState, useEffect } from 'react';
import { Compass, Plus, Search, TrendingUp, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';
import { discoverSearch, addDiscoverPaper, fetchGaps, addGapPaper } from '../services/api';
import { useToast } from '../components/Toast';
import cleanAbstract from '../utils/cleanAbstract';

const TAB_STYLE = (active) => ({
  padding: '10px 24px',
  border: 'none',
  borderBottom: active ? '2px solid var(--astro-primary)' : '2px solid transparent',
  background: 'transparent',
  color: active ? 'var(--astro-primary)' : 'var(--astro-text-muted)',
  fontWeight: active ? 600 : 400,
  fontSize: 'var(--astro-text-sm)',
  cursor: 'pointer',
  transition: 'all 0.15s ease',
});

function GapAnalysis() {
  const [gaps, setGaps] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [added, setAdded] = useState(new Set());
  const [expanded, setExpanded] = useState(new Set());
  const [limit, setLimit] = useState(30);
  const toast = useToast();

  async function loadGaps() {
    setLoading(true);
    try {
      const data = await fetchGaps(limit);
      setGaps(data.gaps || []);
      setStats(data.stats || null);
    } catch (err) {
      console.error(err);
      toast.error('Failed to load gap analysis');
    }
    setLoading(false);
  }

  useEffect(() => {
    loadGaps();
  }, [limit]);

  async function handleAdd(gap) {
    try {
      await addGapPaper({
        doi: gap.doi || '',
        title: gap.title || '',
        authors: gap.authors || '',
        year: gap.year || '',
        url: '',
      });
      setAdded(prev => new Set([...prev, gap.doi || gap.title]));
      toast.success(`Added: ${gap.title?.slice(0, 60) || 'paper'}`);
    } catch (err) {
      toast.error(err.message);
    }
  }

  function toggleExpand(key) {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  if (loading && gaps.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 40, color: 'var(--astro-text-muted)' }}>
        <div style={{ fontSize: 'var(--astro-text-lg)', marginBottom: 8 }}>Analyzing references…</div>
        <div style={{ fontSize: 'var(--astro-text-sm)' }}>This scans all references across your library papers</div>
      </div>
    );
  }

  return (
    <div>
      {stats && (
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: 12, marginBottom: 24,
        }}>
          {[
            { label: 'Papers Missing', value: stats.total_gaps },
            { label: 'Total Citations', value: stats.total_citations },
            { label: 'Avg Citations', value: stats.avg_citations_per_gap },
            { label: 'Most Cited', value: `${stats.top_gap_count}×` },
          ].map(s => (
            <div key={s.label} style={{
              background: 'var(--astro-surface)', border: '1px solid var(--astro-border)',
              borderRadius: 'var(--astro-radius)', padding: '14px 16px', textAlign: 'center',
            }}>
              <div style={{ fontSize: 'var(--astro-text-2xl)', fontWeight: 700, color: 'var(--astro-primary)' }}>
                {typeof s.value === 'number' ? s.value.toLocaleString() : s.value}
              </div>
              <div style={{ fontSize: 'var(--astro-text-xs)', color: 'var(--astro-text-muted)', marginTop: 2 }}>
                {s.label}
              </div>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ fontSize: 'var(--astro-text-sm)', color: 'var(--astro-text-muted)' }}>
          Showing top {gaps.length} frequently cited papers not in your library
        </div>
        <select
          value={limit}
          onChange={e => setLimit(Number(e.target.value))}
          style={{
            padding: '6px 10px', border: '1px solid var(--astro-border)',
            borderRadius: 'var(--astro-radius)', background: 'var(--astro-surface)',
            color: 'var(--astro-text)', fontSize: 'var(--astro-text-sm)',
          }}
        >
          <option value={20}>Top 20</option>
          <option value={30}>Top 30</option>
          <option value={50}>Top 50</option>
          <option value={100}>Top 100</option>
        </select>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {gaps.map((gap, i) => {
          const key = gap.doi || gap.title || i;
          const isAdded = added.has(gap.doi || gap.title);
          const isExpanded = expanded.has(key);

          return (
            <div
              key={key}
              style={{
                background: 'var(--astro-surface)', border: '1px solid var(--astro-border)',
                borderRadius: 'var(--astro-radius-lg)', padding: '16px 20px',
                boxShadow: 'var(--astro-shadow-sm)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{
                      background: 'var(--astro-primary)', color: '#fff',
                      borderRadius: 'var(--astro-radius)', padding: '2px 10px',
                      fontSize: 'var(--astro-text-xs)', fontWeight: 700, flexShrink: 0,
                    }}>
                      {gap.citation_count}×
                    </span>
                    <span style={{ fontWeight: 600, fontSize: 'var(--astro-text-sm)' }}>
                      {gap.title || 'Untitled'}
                    </span>
                  </div>
                  <div style={{
                    fontSize: 'var(--astro-text-xs)', color: 'var(--astro-text-muted)',
                    marginTop: 4, marginLeft: 50,
                  }}>
                    {gap.authors}{gap.year ? ` · ${gap.year}` : ''}{gap.journal ? ` · ${gap.journal}` : ''}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, marginLeft: 12, flexShrink: 0 }}>
                  {gap.doi && (
                    <a
                      href={`https://doi.org/${gap.doi}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      title="Open DOI"
                      style={{
                        padding: '6px 10px', border: '1px solid var(--astro-border)',
                        borderRadius: 'var(--astro-radius)', background: 'var(--astro-surface)',
                        color: 'var(--astro-text-muted)', display: 'flex', alignItems: 'center',
                        textDecoration: 'none',
                      }}
                    >
                      <ExternalLink size={14} />
                    </a>
                  )}
                  <button
                    onClick={() => handleAdd(gap)}
                    disabled={isAdded}
                    style={{
                      padding: '6px 14px', border: '1px solid var(--astro-border)',
                      borderRadius: 'var(--astro-radius)',
                      background: isAdded ? 'var(--astro-success-light, #e6f9ed)' : 'var(--astro-surface)',
                      color: isAdded ? 'var(--astro-success, #22c55e)' : 'var(--astro-text)',
                      fontSize: 'var(--astro-text-sm)', display: 'flex', alignItems: 'center', gap: 4,
                      cursor: isAdded ? 'default' : 'pointer',
                    }}
                  >
                    <Plus size={14} /> {isAdded ? 'Added' : 'Add'}
                  </button>
                </div>
              </div>

              {/* Cited By Section */}
              {gap.cited_by && gap.cited_by.length > 0 && (
                <div style={{ marginTop: 8, marginLeft: 50 }}>
                  <button
                    onClick={() => toggleExpand(key)}
                    style={{
                      background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                      color: 'var(--astro-text-muted)', fontSize: 'var(--astro-text-xs)',
                      display: 'flex', alignItems: 'center', gap: 4,
                    }}
                  >
                    {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    Cited by {gap.cited_by.length} paper{gap.cited_by.length !== 1 ? 's' : ''} in your library
                  </button>
                  {isExpanded && (
                    <ul style={{
                      marginTop: 6, paddingLeft: 16, fontSize: 'var(--astro-text-xs)',
                      color: 'var(--astro-text-secondary)', lineHeight: 1.8,
                    }}>
                      {gap.cited_by.map((t, j) => <li key={j}>{t}</li>)}
                    </ul>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {gaps.length === 0 && !loading && (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--astro-text-muted)' }}>
          <TrendingUp size={48} style={{ opacity: 0.3, marginBottom: 12 }} />
          <div>No gaps found. Add more papers with references to see results.</div>
        </div>
      )}
    </div>
  );
}

export default function Discover() {
  const [tab, setTab] = useState('gaps');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [added, setAdded] = useState(new Set());
  const toast = useToast();

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await discoverSearch(query);
      setResults(data.results || []);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  }

  async function handleAdd(paper) {
    try {
      await addDiscoverPaper(paper);
      setAdded(prev => new Set([...prev, paper.doi || paper.title]));
      toast.success(`Added: ${paper.title?.slice(0, 60) || 'paper'}`);
    } catch (err) {
      toast.error(err.message);
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 'var(--astro-space-6)' }}>
        <h1 style={{ fontSize: 'var(--astro-text-2xl)', fontWeight: 700 }}>
          <Compass size={24} style={{ verticalAlign: 'middle', marginRight: 8 }} />
          Discover
        </h1>
        <p style={{ color: 'var(--astro-text-muted)', fontSize: 'var(--astro-text-sm)', marginTop: 4 }}>
          Find papers missing from your library and search for new ones
        </p>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex', borderBottom: '1px solid var(--astro-border)', marginBottom: 24,
      }}>
        <button onClick={() => setTab('gaps')} style={TAB_STYLE(tab === 'gaps')}>
          <TrendingUp size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
          Frequently Cited
        </button>
        <button onClick={() => setTab('search')} style={TAB_STYLE(tab === 'search')}>
          <Search size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
          Search
        </button>
      </div>

      {/* Gap Analysis Tab */}
      {tab === 'gaps' && <GapAnalysis />}

      {/* Search Tab */}
      {tab === 'search' && (
        <div>
          <form onSubmit={handleSearch} style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search Semantic Scholar for papers…"
              style={{
                flex: 1, padding: '10px 14px', border: '1px solid var(--astro-border)',
                borderRadius: 'var(--astro-radius)', fontSize: 'var(--astro-text-sm)',
                background: 'var(--astro-surface)', color: 'var(--astro-text)',
              }}
            />
            <button
              type="submit"
              disabled={loading}
              style={{
                padding: '10px 24px', background: 'var(--astro-primary)', color: '#fff',
                border: 'none', borderRadius: 'var(--astro-radius)', fontWeight: 600,
                fontSize: 'var(--astro-text-sm)', display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              <Search size={14} /> {loading ? 'Searching…' : 'Search'}
            </button>
          </form>

          {results.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {results.map((r, i) => {
                const key = r.doi || r.title || i;
                const isAdded = added.has(r.doi || r.title);
                return (
                  <div
                    key={key}
                    style={{
                      background: 'var(--astro-surface)', border: '1px solid var(--astro-border)',
                      borderRadius: 'var(--astro-radius-lg)', padding: 20,
                      boxShadow: 'var(--astro-shadow-sm)',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600 }}>{r.title}</div>
                        <div style={{ fontSize: 'var(--astro-text-xs)', color: 'var(--astro-text-muted)', marginTop: 4 }}>
                          {r.authors?.join?.(', ') || r.authors} · {r.year} · {r.venue || r.journal || ''}
                        </div>
                        {r.abstract && (
                          <div style={{ fontSize: 'var(--astro-text-sm)', color: 'var(--astro-text-secondary)', marginTop: 8, lineHeight: 1.6 }}>
                            {cleanAbstract(r.abstract).slice(0, 300)}{r.abstract.length > 300 ? '…' : ''}
                          </div>
                        )}
                      </div>
                      <button
                        onClick={() => handleAdd(r)}
                        disabled={isAdded}
                        style={{
                          padding: '6px 16px', border: '1px solid var(--astro-border)',
                          borderRadius: 'var(--astro-radius)', background: isAdded ? 'var(--astro-success-light)' : 'var(--astro-surface)',
                          color: isAdded ? 'var(--astro-success)' : 'var(--astro-text)',
                          fontSize: 'var(--astro-text-sm)', display: 'flex', alignItems: 'center', gap: 4,
                          cursor: isAdded ? 'default' : 'pointer', marginLeft: 16, flexShrink: 0,
                        }}
                      >
                        <Plus size={14} /> {isAdded ? 'Added' : 'Add'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
