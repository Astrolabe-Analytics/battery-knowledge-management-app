import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, X } from 'lucide-react';
import { fetchPapers } from '../services/api';
import styles from './CommandPalette.module.css';

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef(null);
  const navigate = useNavigate();
  const debounceRef = useRef(null);

  // Ctrl+K / Cmd+K to open
  useEffect(() => {
    function handleKeyDown(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(prev => !prev);
      }
      if (e.key === 'Escape') {
        setOpen(false);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Focus input when opening
  useEffect(() => {
    if (open) {
      setQuery('');
      setResults([]);
      setSelectedIdx(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Search as user types
  useEffect(() => {
    if (!query.trim()) { setResults([]); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setLoading(true);
      fetchPapers({ search: query, limit: 10 })
        .then(data => {
          setResults(data.papers || []);
          setSelectedIdx(0);
        })
        .catch(console.error)
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(debounceRef.current);
  }, [query]);

  function handleSelect(paper) {
    setOpen(false);
    navigate(`/paper/${encodeURIComponent(paper.filename)}`);
  }

  function handleKeyDown(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIdx(i => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && results[selectedIdx]) {
      e.preventDefault();
      handleSelect(results[selectedIdx]);
    }
  }

  if (!open) return null;

  return (
    <div className={styles.overlay} onClick={() => setOpen(false)}>
      <div className={styles.palette} onClick={e => e.stopPropagation()}>
        <div className={styles.inputRow}>
          <Search size={18} className={styles.searchIcon} />
          <input
            ref={inputRef}
            className={styles.input}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search papers…"
          />
          <button className={styles.closeBtn} onClick={() => setOpen(false)}>
            <X size={16} />
          </button>
        </div>

        {query.trim() && (
          <div className={styles.results}>
            {loading ? (
              <div className={styles.noResults}>Searching…</div>
            ) : results.length === 0 ? (
              <div className={styles.noResults}>No papers found</div>
            ) : (
              results.map((p, i) => (
                <div
                  key={p.filename}
                  className={`${styles.result} ${i === selectedIdx ? styles.resultActive : ''}`}
                  onClick={() => handleSelect(p)}
                  onMouseEnter={() => setSelectedIdx(i)}
                >
                  <div className={styles.resultTitle}>{p.title || p.filename}</div>
                  <div className={styles.resultMeta}>
                    {p.authors?.length ? (Array.isArray(p.authors) ? p.authors[0] : p.authors) : ''} · {p.year} · {p.journal || ''}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        <div className={styles.footer}>
          <span className={styles.shortcut}>↑↓</span> navigate
          <span className={styles.shortcut}>↵</span> open
          <span className={styles.shortcut}>esc</span> close
        </div>
      </div>
    </div>
  );
}
