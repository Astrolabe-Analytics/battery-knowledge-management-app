import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpDown, BookCheck, BookX, ChevronLeft, ChevronRight, Plus, Trash2, FolderOpen, Zap, RefreshCw } from 'lucide-react';
import { fetchPapers, fetchFilters, deletePapers, fetchCollections, addPapersToCollectionBulk, fetchMatchingFilenames, fetchEnrichmentStatus, enrichPapersStream, enrichPapers } from '../services/api';
import { useToast } from '../components/Toast';
import ImportModal from '../components/ImportModal';
import styles from './Library.module.css';

const PAGE_SIZE = 50;

export default function Library() {
  const [papers, setPapers] = useState([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({});
  const [loading, setLoading] = useState(true);

  // Filter state
  const [search, setSearch] = useState('');
  const [chemistry, setChemistry] = useState('');
  const [topic, setTopic] = useState('');
  const [paperType, setPaperType] = useState('');
  const [status, setStatus] = useState('');

  // Sort & pagination
  const [sortKey, setSortKey] = useState('date_added');
  const [sortDir, setSortDir] = useState('desc');
  const [page, setPage] = useState(0);

  // Debounce search
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const debounceRef = useRef(null);

  // Import modal
  const [importOpen, setImportOpen] = useState(false);

  // Bulk select
  const [selected, setSelected] = useState(new Set());
  const [allResultsSelected, setAllResultsSelected] = useState(false);
  const [collections, setCollections] = useState([]);
  const [bulkCollectionId, setBulkCollectionId] = useState('');
  const toast = useToast();

  // Enrichment state
  const [enrichStatus, setEnrichStatus] = useState(null);
  const [enriching, setEnriching] = useState(false);
  const [enrichProgress, setEnrichProgress] = useState(null);
  const enrichAbortRef = useRef(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(0);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [search]);

  // Reset page when filters change
  useEffect(() => { setPage(0); }, [chemistry, topic, paperType, status]);

  // Load filters once
  useEffect(() => {
    fetchFilters().then(setFilters).catch(console.error);
  }, []);

  // Fetch papers from server (paginated)
  const loadPapers = useCallback(() => {
    setLoading(true);
    const params = {
      offset: page * PAGE_SIZE,
      limit: PAGE_SIZE,
      sort: sortKey,
      sort_dir: sortDir,
    };
    if (debouncedSearch) params.search = debouncedSearch;
    if (chemistry) params.chemistry = chemistry;
    if (topic) params.topic = topic;
    if (paperType) params.paper_type = paperType;
    if (status) params.status = status;

    fetchPapers(params)
      .then(data => {
        setPapers(data.papers || []);
        setTotal(data.total || 0);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, sortKey, sortDir, debouncedSearch, chemistry, topic, paperType, status]);

  useEffect(() => { loadPapers(); }, [loadPapers]);

  // Load collections for bulk assignment
  useEffect(() => {
    fetchCollections()
      .then(data => setCollections(data.collections || []))
      .catch(console.error);
  }, []);

  // Load enrichment status
  const loadEnrichStatus = useCallback(() => {
    fetchEnrichmentStatus()
      .then(setEnrichStatus)
      .catch(console.error);
  }, []);

  useEffect(() => { loadEnrichStatus(); }, [loadEnrichStatus]);

  // Clear selection on page change (only if not selecting all results)
  useEffect(() => {
    if (!allResultsSelected) setSelected(new Set());
  }, [page]);

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
    setAllResultsSelected(false);
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename); else next.add(filename);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selected.size === papers.length) {
      setSelected(new Set());
      setAllResultsSelected(false);
    } else {
      setSelected(new Set(papers.map(p => p.filename)));
      // Don't auto-set allResultsSelected; user must click the banner
    }
  }

  async function selectAllResults() {
    try {
      const params = {};
      if (debouncedSearch) params.search = debouncedSearch;
      if (chemistry) params.chemistry = chemistry;
      if (topic) params.topic = topic;
      if (paperType) params.paper_type = paperType;
      if (status) params.status = status;
      const data = await fetchMatchingFilenames(params);
      setSelected(new Set(data.filenames));
      setAllResultsSelected(true);
    } catch (e) {
      toast.error('Failed to select all results');
    }
  }

  function clearSelection() {
    setSelected(new Set());
    setAllResultsSelected(false);
  }

  async function handleBulkDelete() {
    if (!selected.size) return;
    if (!confirm(`Delete ${selected.size} paper(s)?`)) return;
    try {
      await deletePapers([...selected]);
      toast.success(`Deleted ${selected.size} paper(s)`);
      clearSelection();
      loadPapers();
    } catch (e) {
      toast.error('Failed to delete papers');
    }
  }

  async function handleBulkAddCollection() {
    if (!bulkCollectionId || !selected.size) return;
    const colId = Number(bulkCollectionId);
    const col = collections.find(c => c.id === colId);
    try {
      const result = await addPapersToCollectionBulk(colId, [...selected]);
      toast.success(`Added ${result.added} paper(s) to ${col?.name || 'collection'}${result.skipped ? ` (${result.skipped} already in collection)` : ''}`);
    } catch (e) {
      toast.error('Failed to add papers to collection');
    }
    setBulkCollectionId('');
    clearSelection();
  }

  function handleEnrichAll(maxPapers) {
    if (enriching) return;
    setEnriching(true);
    setEnrichProgress({ index: 0, total: 0, enriched: 0, failed: 0 });

    const abort = enrichPapersStream({
      maxPapers: maxPapers || undefined,
      onProgress(data) {
        setEnrichProgress({
          index: data.index,
          total: data.total,
          enriched: data.enriched,
          failed: data.failed,
          title: data.title,
          result: data.result,
        });
      },
      onDone(data) {
        setEnriching(false);
        setEnrichProgress(null);
        toast.success(`Enrichment complete: ${data.enriched} enriched, ${data.failed} failed out of ${data.total}`);
        loadPapers();
        loadEnrichStatus();
      },
      onError(err) {
        setEnriching(false);
        setEnrichProgress(null);
        toast.error(`Enrichment error: ${err.message}`);
      },
    });
    enrichAbortRef.current = abort;
  }

  function handleCancelEnrich() {
    if (enrichAbortRef.current) {
      enrichAbortRef.current();
      enrichAbortRef.current = null;
    }
    setEnriching(false);
    setEnrichProgress(null);
    toast.info('Enrichment cancelled');
    loadPapers();
    loadEnrichStatus();
  }

  async function handleEnrichSelected() {
    if (!selected.size) return;
    try {
      setEnriching(true);
      const res = await enrichPapers([...selected]);
      toast.success(`Enriched ${res.enriched} of ${res.total} paper(s)`);
      clearSelection();
      loadPapers();
      loadEnrichStatus();
    } catch (e) {
      toast.error('Enrichment failed: ' + e.message);
    } finally {
      setEnriching(false);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>
          Papers
          <span className={styles.count}>({total})</span>
        </h1>
        <button className={styles.importBtn} onClick={() => setImportOpen(true)}>
          <Plus size={16} /> Import
        </button>
      </div>

      <ImportModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={() => { setImportOpen(false); loadPapers(); loadEnrichStatus(); }}
      />

      {/* Enrichment status banner */}
      {enrichStatus && enrichStatus.needs_enrichment > 0 && !enriching && (
        <div className={styles.enrichBanner}>
          <div className={styles.enrichInfo}>
            <Zap size={16} />
            <span>
              <strong>{enrichStatus.needs_enrichment}</strong> papers need metadata enrichment
              {enrichStatus.breakdown && (
                <span className={styles.enrichBreakdown}>
                  ({enrichStatus.breakdown.has_doi} with DOI,{' '}
                  {enrichStatus.breakdown.has_url} with URL,{' '}
                  {enrichStatus.breakdown.has_title_only} title-only)
                </span>
              )}
            </span>
          </div>
          <div className={styles.enrichActions}>
            <button
              className={styles.enrichBtn}
              onClick={() => handleEnrichAll(50)}
              title="Enrich up to 50 papers"
            >
              <Zap size={14} /> Enrich 50
            </button>
            <button
              className={styles.enrichBtnAll}
              onClick={() => handleEnrichAll()}
              title="Enrich all incomplete papers"
            >
              <Zap size={14} /> Enrich All
            </button>
          </div>
        </div>
      )}

      {/* Enrichment progress */}
      {enriching && enrichProgress && (
        <div className={styles.enrichProgress}>
          <div className={styles.enrichProgressHeader}>
            <RefreshCw size={14} className={styles.spinning} />
            <span>
              Enriching {enrichProgress.index}/{enrichProgress.total}
              {enrichProgress.title && <> — {enrichProgress.title}</>}
            </span>
            <button className={styles.cancelBtn} onClick={handleCancelEnrich}>Cancel</button>
          </div>
          <div className={styles.enrichProgressBar}>
            <div
              className={styles.enrichProgressFill}
              style={{ width: enrichProgress.total > 0 ? `${(enrichProgress.index / enrichProgress.total) * 100}%` : '0%' }}
            />
          </div>
          <div className={styles.enrichStats}>
            <span className={styles.enrichStatGood}>{enrichProgress.enriched} enriched</span>
            <span className={styles.enrichStatBad}>{enrichProgress.failed} failed</span>
          </div>
        </div>
      )}

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className={styles.bulkBar}>
          <span className={styles.bulkCount}>{selected.size} selected</span>

          {/* "Select all results" banner — shows when current page is fully selected but total results > page size */}
          {!allResultsSelected && selected.size === papers.length && total > papers.length && (
            <button className={styles.selectAllBtn} onClick={selectAllResults}>
              Select all {total} matching results
            </button>
          )}
          {allResultsSelected && (
            <button className={styles.selectAllBtn} onClick={clearSelection}>
              Clear selection
            </button>
          )}

          <select
            className={styles.filterSelect}
            value={bulkCollectionId}
            onChange={e => setBulkCollectionId(e.target.value)}
          >
            <option value="">Add to collection…</option>
            {collections.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <button className={styles.bulkBtn} onClick={handleBulkAddCollection} disabled={!bulkCollectionId}>
            <FolderOpen size={14} /> Assign
          </button>
          <button className={styles.bulkBtn} onClick={handleEnrichSelected} disabled={enriching}>
            <Zap size={14} /> Enrich Selected
          </button>
          <button className={styles.bulkBtnDanger} onClick={handleBulkDelete}>
            <Trash2 size={14} /> Delete
          </button>
        </div>
      )}

      {/* Filters */}
      <div className={styles.filters}>
        <input
          className={styles.searchInput}
          placeholder="Search papers…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <Select
          value={chemistry}
          onChange={setChemistry}
          placeholder="Chemistry"
          options={filters.chemistries || []}
        />
        <Select
          value={topic}
          onChange={setTopic}
          placeholder="Topic"
          options={filters.topics || []}
        />
        <Select
          value={paperType}
          onChange={setPaperType}
          placeholder="Type"
          options={filters.paper_types || []}
        />
        <Select
          value={status}
          onChange={setStatus}
          placeholder="Status"
          options={['AI Summary', 'Complete', 'Metadata Only', 'Incomplete']}
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
          <div className={styles.empty}>No papers match your filters.</div>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.colCheckbox}>
                  <input
                    type="checkbox"
                    checked={papers.length > 0 && (allResultsSelected || selected.size === papers.length)}
                    onChange={allResultsSelected ? clearSelection : toggleSelectAll}
                  />
                </th>
                <SortTh k="title" label="Title" className={styles.colTitle} sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} />
                <SortTh k="authors" label="Authors" className={styles.colAuthors} sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} />
                <SortTh k="year" label="Year" className={styles.colYear} sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} />
                <SortTh k="journal" label="Journal" className={styles.colJournal} sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} />
                <SortTh k="paper_type" label="Type" className={styles.colType} sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} />
                <SortTh k="status" label="Status" className={styles.colStatus} sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} />
                <th className={styles.colRead}>Read</th>
                <SortTh k="date_added" label="Added" className={styles.colAdded} sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} />
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
                  <td>{p.journal}</td>
                  <td><span className={styles.badge}>{p.paper_type}</span></td>
                  <td><span className={statusClass(p.status)}>{p.status}</span></td>
                  <td>
                    {p.read
                      ? <BookCheck size={16} className={styles.badgeRead} />
                      : <BookX size={16} className={styles.badgeUnread} />}
                  </td>
                  <td>{p.date_added?.slice(0, 10)}</td>
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

function statusClass(status) {
  switch (status) {
    case 'Complete': return styles.statusComplete;
    case 'AI Summary': return styles.statusAiSummary;
    case 'Metadata Only': return styles.statusMetadata;
    case 'Incomplete': return styles.statusIncomplete;
    default: return styles.badge;
  }
}

function formatAuthors(raw) {
  if (!raw) return '';
  const list = Array.isArray(raw) ? raw : [raw];
  if (list.length <= 2) return list.join(', ');
  return `${list[0]} et al.`;
}

function Select({ value, onChange, placeholder, options }) {
  return (
    <select
      className={styles.filterSelect}
      value={value}
      onChange={e => onChange(e.target.value)}
    >
      <option value="">{placeholder}</option>
      {options.map(o => (
        <option key={o} value={o}>{o}</option>
      ))}
    </select>
  );
}

function SortTh({ k, label, sortKey, sortDir, onClick, className }) {
  const active = sortKey === k;
  return (
    <th onClick={() => onClick(k)} className={className}>
      {label}
      <ArrowUpDown
        size={12}
        className={styles.sortIcon}
        style={active ? { opacity: 1 } : undefined}
      />
    </th>
  );
}
