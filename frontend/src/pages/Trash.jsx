import { useState, useEffect, useCallback } from 'react';
import { Trash2, RotateCcw, AlertTriangle, FileText } from 'lucide-react';
import { fetchTrash, restorePapers, emptyTrash, hardDeletePaper } from '../services/api';
import { useToast } from '../components/Toast';

export default function Trash() {
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(new Set());
  const [actionLoading, setActionLoading] = useState(false);
  const toast = useToast();

  const load = useCallback(async () => {
    try {
      const data = await fetchTrash();
      setPapers(data.papers || []);
    } catch (e) {
      console.error(e);
      toast.error('Failed to load trash');
    }
    setLoading(false);
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  function toggleSelect(filename) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selected.size === papers.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(papers.map(p => p.filename)));
    }
  }

  async function handleRestore() {
    if (selected.size === 0) return;
    setActionLoading(true);
    try {
      await restorePapers([...selected]);
      toast.success(`Restored ${selected.size} paper(s)`);
      setSelected(new Set());
      await load();
    } catch (e) {
      toast.error(e.message);
    }
    setActionLoading(false);
  }

  async function handleEmptyTrash() {
    if (!confirm(`Permanently delete all ${papers.length} trashed papers? This cannot be undone.`)) return;
    setActionLoading(true);
    try {
      const res = await emptyTrash();
      toast.success(`Permanently deleted ${res.deleted} paper(s)`);
      setSelected(new Set());
      await load();
    } catch (e) {
      toast.error(e.message);
    }
    setActionLoading(false);
  }

  async function handleHardDelete(filename) {
    if (!confirm('Permanently delete this paper? This cannot be undone.')) return;
    setActionLoading(true);
    try {
      await hardDeletePaper(filename);
      toast.success('Paper permanently deleted');
      setSelected(prev => { const n = new Set(prev); n.delete(filename); return n; });
      await load();
    } catch (e) {
      toast.error(e.message);
    }
    setActionLoading(false);
  }

  function formatDate(iso) {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleDateString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch { return iso; }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60, color: 'var(--astro-text-muted)' }}>
        Loading trash…
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 'var(--astro-text-2xl)', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 10 }}>
          <Trash2 size={24} />
          Trash
          {papers.length > 0 && (
            <span style={{
              fontSize: 'var(--astro-text-sm)', fontWeight: 400,
              color: 'var(--astro-text-muted)', marginLeft: 4,
            }}>
              ({papers.length})
            </span>
          )}
        </h1>
        <div style={{ display: 'flex', gap: 8 }}>
          {selected.size > 0 && (
            <button
              onClick={handleRestore}
              disabled={actionLoading}
              style={{
                padding: '8px 16px', background: 'var(--astro-primary)',
                border: 'none', borderRadius: 'var(--astro-radius)',
                color: '#fff', fontSize: 'var(--astro-text-sm)',
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
                opacity: actionLoading ? 0.6 : 1,
              }}
            >
              <RotateCcw size={14} /> Restore {selected.size}
            </button>
          )}
          {papers.length > 0 && (
            <button
              onClick={handleEmptyTrash}
              disabled={actionLoading}
              style={{
                padding: '8px 16px', background: 'transparent',
                border: '1px solid var(--astro-danger)',
                borderRadius: 'var(--astro-radius)', color: 'var(--astro-danger)',
                fontSize: 'var(--astro-text-sm)', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 6,
                opacity: actionLoading ? 0.6 : 1,
              }}
            >
              <AlertTriangle size={14} /> Empty Trash
            </button>
          )}
        </div>
      </div>

      {/* Empty state */}
      {papers.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: 60, color: 'var(--astro-text-muted)',
          background: 'var(--astro-surface)', borderRadius: 'var(--astro-radius)',
          border: '1px solid var(--astro-border)',
        }}>
          <Trash2 size={40} style={{ marginBottom: 12, opacity: 0.4 }} />
          <div style={{ fontSize: 'var(--astro-text-lg)', fontWeight: 500, marginBottom: 4 }}>
            Trash is empty
          </div>
          <div style={{ fontSize: 'var(--astro-text-sm)' }}>
            Deleted papers will appear here for recovery.
          </div>
        </div>
      ) : (
        <>
          {/* Select all row */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '8px 12px', marginBottom: 8,
            fontSize: 'var(--astro-text-sm)', color: 'var(--astro-text-muted)',
          }}>
            <input
              type="checkbox"
              checked={selected.size === papers.length}
              onChange={toggleSelectAll}
              style={{ cursor: 'pointer' }}
            />
            <span>Select all</span>
          </div>

          {/* Paper list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {papers.map(p => (
              <div
                key={p.filename}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  background: selected.has(p.filename) ? 'var(--astro-primary-bg, rgba(99,102,241,0.08))' : 'var(--astro-surface)',
                  border: '1px solid var(--astro-border)',
                  borderRadius: 'var(--astro-radius)', padding: '12px 16px',
                  transition: 'background 0.15s',
                }}
              >
                <input
                  type="checkbox"
                  checked={selected.has(p.filename)}
                  onChange={() => toggleSelect(p.filename)}
                  style={{ cursor: 'pointer', flexShrink: 0 }}
                />
                <FileText size={18} style={{ color: 'var(--astro-text-muted)', flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontWeight: 500, fontSize: 'var(--astro-text-sm)',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>
                    {p.title || p.filename}
                  </div>
                  <div style={{
                    fontSize: 'var(--astro-text-xs)', color: 'var(--astro-text-muted)',
                    marginTop: 2, display: 'flex', gap: 12,
                  }}>
                    {p.journal && p.journal !== 'Unknown' && <span>{p.journal}</span>}
                    {p.year && <span>{p.year}</span>}
                    <span>Deleted {formatDate(p.deleted_at)}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  <button
                    onClick={() => restorePapers([p.filename]).then(() => { toast.success('Restored'); load(); })}
                    title="Restore"
                    style={{
                      background: 'transparent', border: 'none', cursor: 'pointer',
                      color: 'var(--astro-primary)', padding: 4,
                    }}
                  >
                    <RotateCcw size={16} />
                  </button>
                  <button
                    onClick={() => handleHardDelete(p.filename)}
                    title="Delete permanently"
                    style={{
                      background: 'transparent', border: 'none', cursor: 'pointer',
                      color: 'var(--astro-danger)', padding: 4,
                    }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
