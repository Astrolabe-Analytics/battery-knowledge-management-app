import { useState, useEffect } from 'react';
import { Clock, Star, Trash2 } from 'lucide-react';
import { fetchHistory, toggleStar, deleteQuery, clearHistory } from '../services/api';

export default function History() {
  const [queries, setQueries] = useState([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const data = await fetchHistory({ limit: 100 });
      setQueries(data.queries || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function handleStar(id) {
    await toggleStar(id);
    load();
  }

  async function handleDelete(id) {
    await deleteQuery(id);
    load();
  }

  async function handleClear() {
    if (!confirm('Clear all history?')) return;
    await clearHistory();
    load();
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 40, color: 'var(--astro-text-muted)' }}>Loading…</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 'var(--astro-text-2xl)', fontWeight: 700 }}>
          <Clock size={24} style={{ verticalAlign: 'middle', marginRight: 8 }} />
          Query History
        </h1>
        {queries.length > 0 && (
          <button
            onClick={handleClear}
            style={{
              padding: '8px 16px', background: 'transparent', border: '1px solid var(--astro-danger)',
              borderRadius: 'var(--astro-radius)', color: 'var(--astro-danger)',
              fontSize: 'var(--astro-text-sm)', cursor: 'pointer',
            }}
          >
            Clear All
          </button>
        )}
      </div>

      {queries.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--astro-text-muted)' }}>
          No query history yet.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {queries.map(q => (
            <div
              key={q.id}
              style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                background: 'var(--astro-surface)', border: '1px solid var(--astro-border)',
                borderRadius: 'var(--astro-radius)', padding: '12px 16px',
              }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500, fontSize: 'var(--astro-text-sm)' }}>{q.question}</div>
                <div style={{ fontSize: 'var(--astro-text-xs)', color: 'var(--astro-text-muted)', marginTop: 2 }}>
                  {q.timestamp} · {q.num_sources} sources
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={() => handleStar(q.id)}
                  style={{
                    background: 'transparent', border: 'none', cursor: 'pointer',
                    color: q.starred ? 'var(--astro-warning)' : 'var(--astro-text-muted)',
                  }}
                >
                  <Star size={16} fill={q.starred ? 'currentColor' : 'none'} />
                </button>
                <button
                  onClick={() => handleDelete(q.id)}
                  style={{
                    background: 'transparent', border: 'none', cursor: 'pointer',
                    color: 'var(--astro-text-muted)',
                  }}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
