import { useState } from 'react';
import { Compass, Plus, Search } from 'lucide-react';
import { discoverSearch, addDiscoverPaper } from '../services/api';
import { useToast } from '../components/Toast';
import cleanAbstract from '../utils/cleanAbstract';

export default function Discover() {
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
          Search Semantic Scholar for new papers to add to your library
        </p>
      </div>

      <form onSubmit={handleSearch} style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search for papers…"
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
  );
}
