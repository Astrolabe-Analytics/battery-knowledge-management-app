import { useState, useEffect, useCallback, useRef } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, ArrowUpDown, BookCheck, BookX, ChevronLeft, ChevronRight,
  FolderOpen, Pencil, Save, Trash2, X,
} from 'lucide-react';
import {
  fetchPapers, fetchCollections, removePaperFromCollection,
  deleteCollection, updateCollection,
} from '../services/api';
import { useToast } from '../components/Toast';
import styles from './CollectionDetail.module.css';

const PAGE_SIZE = 50;

export default function CollectionDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();

  const [collection, setCollection] = useState(null);
  const [papers, setPapers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Search, sort, pagination
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const debounceRef = useRef(null);
  const [sortKey, setSortKey] = useState('date_added');
  const [sortDir, setSortDir] = useState('desc');
  const [page, setPage] = useState(0);

  // Bulk select
  const [selected, setSelected] = useState(new Set());

  // Inline edit
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDesc, setEditDesc] = useState('');

  // Debounce search
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(0);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [search]);

  // Load collection info
  const loadCollection = useCallback(async () => {
    try {
      const data = await fetchCollections();
      const col = (data.collections || []).find(c => c.id === Number(id));
      if (col) {
        setCollection(col);
        setEditName(col.name);
        setEditDesc(col.description || '');
      }
    } catch (e) { console.error(e); }
  }, [id]);

  useEffect(() => { loadCollection(); }, [loadCollection]);

  // Load papers in this collection
  const loadPapers = useCallback(() => {
    if (!collection) return;
    setLoading(true);
    const params = {
      collection: collection.name,
      offset: page * PAGE_SIZE,
      limit: PAGE_SIZE,
      sort: sortKey,
      sort_dir: sortDir,
    };
    if (debouncedSearch) params.search = debouncedSearch;

    fetchPapers(params)
      .then(data => {
        setPapers(data.papers || []);
        setTotal(data.total || 0);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [collection, page, sortKey, sortDir, debouncedSearch]);

  useEffect(() => { loadPapers(); }, [loadPapers]);

  // Clear selection on page change
  useEffect(() => { setSelected(new Set()); }, [page]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  function toggleSort(key) {
    if (sortKey === key) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
    setPage(0);
  }

  function toggleSelect(filename) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename); else next.add(filename);
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

  async function handleRemove(filename) {
    try {
      await removePaperFromCollection(Number(id), filename);
      toast.success('Removed from collection');
      loadPapers();
      loadCollection();
    } catch (e) {
      toast.error('Failed to remove paper');
    }
  }

  async function handleBulkRemove() {
    if (!selected.size) return;
    if (!confirm(`Remove ${selected.size} paper(s) from this collection?`)) return;
    let ok = 0;
    for (const fn of selected) {
      try {
        await removePaperFromCollection(Number(id), fn);
        ok++;
      } catch (e) { /* skip */ }
    }
    toast.success(`Removed ${ok} paper(s) from collection`);
    setSelected(new Set());
    loadPapers();
    loadCollection();
  }

  async function handleDeleteCollection() {
    if (!confirm(`Delete collection "${collection?.name}"? Papers won't be deleted.`)) return;
    try {
      await deleteCollection(Number(id));
      toast.success(`Deleted "${collection?.name}"`);
      navigate('/collections');
    } catch (e) {
      toast.error('Failed to delete collection');
    }
  }

  async function handleSaveEdit() {
    try {
      await updateCollection(Number(id), {
        name: editName.trim(),
        description: editDesc.trim(),
      });
      toast.success('Collection updated');
      setEditing(false);
      loadCollection();
    } catch (e) {
      toast.error('Failed to update collection');
    }
  }

  if (!collection && !loading) {
    return (
      <div className={styles.page}>
        <Link to="/collections" className={styles.backLink}>
          <ArrowLeft size={16} /> Back to Collections
        </Link>
        <div className={styles.empty}>Collection not found.</div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <Link to="/collections" className={styles.backLink}>
        <ArrowLeft size={16} /> Back to Collections
      </Link>

      {/* Collection header */}
      <div className={styles.header}>
        {editing ? (
          <div className={styles.editForm}>
            <input
              className={styles.editInput}
              value={editName}
              onChange={e => setEditName(e.target.value)}
              placeholder="Collection name"
            />
            <input
              className={styles.editInput}
              value={editDesc}
              onChange={e => setEditDesc(e.target.value)}
              placeholder="Description (optional)"
              style={{ flex: 2 }}
            />
            <button className={styles.saveBtn} onClick={handleSaveEdit}>
              <Save size={14} /> Save
            </button>
            <button className={styles.cancelBtn} onClick={() => setEditing(false)}>
              <X size={14} /> Cancel
            </button>
          </div>
        ) : (
          <>
            <div className={styles.headerInfo}>
              <FolderOpen size={22} className={styles.headerIcon} />
              <h1 className={styles.title}>{collection?.name}</h1>
              <span className={styles.count}>{total} papers</span>
            </div>
            {collection?.description && (
              <p className={styles.description}>{collection.description}</p>
            )}
            <div className={styles.headerActions}>
              <button className={styles.editBtn} onClick={() => setEditing(true)}>
                <Pencil size={14} /> Edit
              </button>
              <button className={styles.deleteBtn} onClick={handleDeleteCollection}>
                <Trash2 size={14} /> Delete Collection
              </button>
            </div>
          </>
        )}
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className={styles.bulkBar}>
          <span className={styles.bulkCount}>{selected.size} selected</span>
          <button className={styles.bulkBtnDanger} onClick={handleBulkRemove}>
            <Trash2 size={14} /> Remove from Collection
          </button>
        </div>
      )}

      {/* Search */}
      <div className={styles.searchRow}>
        <input
          className={styles.searchInput}
          placeholder="Search within collection…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {/* Table */}
      <div className={styles.tableWrap}>
        {loading ? (
          <div className={styles.loading}>
            <div className={styles.progressBar}>
              <div className={styles.progressFill} />
            </div>
            <span>Loading papers…</span>
          </div>
        ) : papers.length === 0 ? (
          <div className={styles.empty}>
            {debouncedSearch ? 'No papers match your search.' : 'No papers in this collection yet.'}
          </div>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input
                    type="checkbox"
                    checked={papers.length > 0 && selected.size === papers.length}
                    onChange={toggleSelectAll}
                  />
                </th>
                <SortTh k="title" label="Title" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} />
                <SortTh k="authors" label="Authors" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} />
                <SortTh k="year" label="Year" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} />
                <SortTh k="paper_type" label="Type" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} />
                <th>Read</th>
                <th style={{ width: 80 }}></th>
              </tr>
            </thead>
            <tbody>
              {papers.map(p => (
                <tr key={p.filename} className={selected.has(p.filename) ? styles.selectedRow : undefined}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.has(p.filename)}
                      onChange={() => toggleSelect(p.filename)}
                    />
                  </td>
                  <td className={styles.titleCell}>
                    <Link
                      to={`/paper/${encodeURIComponent(p.filename)}`}
                      className={styles.titleLink}
                      title={p.title}
                    >
                      {p.title || p.filename}
                    </Link>
                  </td>
                  <td>{formatAuthors(p.authors)}</td>
                  <td>{p.year}</td>
                  <td><span className={styles.badge}>{p.paper_type}</span></td>
                  <td>
                    {p.read
                      ? <BookCheck size={16} className={styles.badgeRead} />
                      : <BookX size={16} className={styles.badgeUnread} />}
                  </td>
                  <td>
                    <button
                      className={styles.removeBtn}
                      onClick={() => handleRemove(p.filename)}
                      title="Remove from collection"
                    >
                      <X size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button
            className={styles.pageBtn}
            disabled={page === 0}
            onClick={() => setPage(p => p - 1)}
          >
            <ChevronLeft size={16} /> Prev
          </button>
          <span className={styles.pageInfo}>
            Page {page + 1} of {totalPages}
          </span>
          <button
            className={styles.pageBtn}
            disabled={page >= totalPages - 1}
            onClick={() => setPage(p => p + 1)}
          >
            Next <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

/* ---------- helpers ---------- */

function formatAuthors(raw) {
  if (!raw) return '';
  const list = Array.isArray(raw) ? raw : [raw];
  if (list.length <= 2) return list.join(', ');
  return `${list[0]} et al.`;
}

function SortTh({ k, label, sortKey, sortDir, onClick }) {
  const active = sortKey === k;
  return (
    <th onClick={() => onClick(k)} style={{ cursor: 'pointer' }}>
      {label}
      <ArrowUpDown
        size={12}
        style={{ marginLeft: 4, opacity: active ? 1 : 0.3 }}
      />
    </th>
  );
}
