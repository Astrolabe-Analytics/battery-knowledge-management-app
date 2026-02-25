import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { FolderOpen, Plus, Trash2, ChevronRight } from 'lucide-react';
import { fetchCollections, createCollection, deleteCollection } from '../services/api';
import { useToast } from '../components/Toast';

export default function Collections() {
  const [collections, setCollections] = useState([]);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  async function load() {
    try {
      const data = await fetchCollections();
      setCollections(data.collections || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e) {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      await createCollection({ name: newName.trim(), description: newDesc.trim() || undefined });
      toast.success(`Collection "${newName.trim()}" created`);
      setNewName('');
      setNewDesc('');
      load();
    } catch (e) {
      toast.error('Failed to create collection');
    }
  }

  async function handleDelete(id, name) {
    if (!confirm(`Delete collection "${name}"?`)) return;
    try {
      await deleteCollection(id);
      toast.success(`Deleted "${name}"`);
      load();
    } catch (e) {
      toast.error('Failed to delete collection');
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 40, color: 'var(--astro-text-muted)' }}>Loading…</div>;

  return (
    <div>
      <h1 style={{ fontSize: 'var(--astro-text-2xl)', fontWeight: 700, marginBottom: 24 }}>
        <FolderOpen size={24} style={{ verticalAlign: 'middle', marginRight: 8 }} />
        Collections
      </h1>

      <form onSubmit={handleCreate} style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
        <input
          value={newName}
          onChange={e => setNewName(e.target.value)}
          placeholder="Collection name…"
          style={{
            flex: 1, minWidth: 180, padding: '10px 14px', border: '1px solid var(--astro-border)',
            borderRadius: 'var(--astro-radius)', fontSize: 'var(--astro-text-sm)',
            background: 'var(--astro-surface)', color: 'var(--astro-text)',
          }}
        />
        <input
          value={newDesc}
          onChange={e => setNewDesc(e.target.value)}
          placeholder="Description (optional)"
          style={{
            flex: 1, minWidth: 180, padding: '10px 14px', border: '1px solid var(--astro-border)',
            borderRadius: 'var(--astro-radius)', fontSize: 'var(--astro-text-sm)',
            background: 'var(--astro-surface)', color: 'var(--astro-text)',
          }}
        />
        <button
          type="submit"
          style={{
            padding: '10px 20px', background: 'var(--astro-primary)', color: '#fff',
            border: 'none', borderRadius: 'var(--astro-radius)', fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
          }}
        >
          <Plus size={14} /> Create
        </button>
      </form>

      {collections.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--astro-text-muted)' }}>
          No collections yet. Create one above.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {collections.map(c => (
            <div
              key={c.id}
              style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                background: 'var(--astro-surface)', border: '1px solid var(--astro-border)',
                borderRadius: 'var(--astro-radius-lg)', padding: '16px 20px',
              }}
            >
              <Link
                to={`/collections/${c.id}`}
                style={{
                  flex: 1, textDecoration: 'none', color: 'inherit',
                  display: 'flex', alignItems: 'center', gap: 12,
                }}
              >
                <FolderOpen size={18} style={{ color: 'var(--astro-primary)', flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600 }}>{c.name}</div>
                  <div style={{ fontSize: 'var(--astro-text-xs)', color: 'var(--astro-text-muted)' }}>
                    {c.paper_count || 0} papers{c.description ? ` · ${c.description}` : ''}
                  </div>
                </div>
                <ChevronRight size={16} style={{ color: 'var(--astro-text-muted)', flexShrink: 0 }} />
              </Link>
              <div style={{ display: 'flex', gap: 8, marginLeft: 12 }}>
                <button
                  onClick={() => handleDelete(c.id, c.name)}
                  style={{
                    padding: '6px 12px', background: 'transparent', border: '1px solid var(--astro-border)',
                    borderRadius: 'var(--astro-radius)', color: 'var(--astro-danger)', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 4, fontSize: 'var(--astro-text-sm)',
                  }}
                >
                  <Trash2 size={14} /> Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
