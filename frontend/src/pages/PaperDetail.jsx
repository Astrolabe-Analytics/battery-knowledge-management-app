import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Calendar, BookOpen, FileText,
  Sparkles, StickyNote, BookCheck, BookX,
  Plus, X, Pencil, Save, XCircle, Download, Check, Loader, ExternalLink,
  Zap,
} from 'lucide-react';
import {
  fetchPaperDetail, updateNotes, toggleRead, fetchReferences, getPdfUrl,
  fetchCollections, addPaperToCollection, removePaperFromCollection,
  updateMetadata, importMetadataOnly, enrichSinglePaper, enrichFromCrossref,
} from '../services/api';
import { useToast } from '../components/Toast';
import cleanAbstract from '../utils/cleanAbstract';
import styles from './PaperDetail.module.css';

/** Render a Crossref-style reference as structured citation JSX. */
function RefCitation({ r }) {
  // If there's a pre-formatted "unstructured" field, use it
  if (r.unstructured) return <span className={styles.refText}>{r.unstructured}</span>;

  const title = r['article-title'] || r['volume-title'] || r['series-title'];
  const journal = r['journal-title'];
  const author = r.author;
  const year = r.year;
  const volume = r.volume;
  const firstPage = r['first-page'];
  const issue = r.issue;

  // If we have basically nothing structured, show DOI or raw JSON
  if (!title && !author && !journal) {
    if (r.DOI) return <span className={styles.refText}>DOI: {r.DOI}</span>;
    return <span className={styles.refText}>{JSON.stringify(r)}</span>;
  }

  return (
    <span className={styles.refText}>
      {author && <span className={styles.refAuthor}>{author}{year ? '' : '.'} </span>}
      {year && <span className={styles.refYear}>({year}). </span>}
      {title && <span className={styles.refTitle}>“{title}.” </span>}
      {journal && (
        <span className={styles.refJournal}>
          <em>{journal}</em>
          {volume && <>, <strong>{volume}</strong></>}
          {issue && <>({issue})</>}
          {firstPage && <>, pp. {firstPage}</>}
          .{' '}
        </span>
      )}
      {!journal && r['series-title'] && title !== r['series-title'] && (
        <span className={styles.refJournal}><em>{r['series-title']}</em>. </span>
      )}
    </span>
  );
}

export default function PaperDetail() {
  const { filename } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [paper, setPaper] = useState(null);
  const [notes, setNotes] = useState('');
  const [read, setRead] = useState(false);
  const [refs, setRefs] = useState([]);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  // Collections
  const [collections, setCollections] = useState([]);
  const [paperCollections, setPaperCollections] = useState([]);
  const [addCollectionId, setAddCollectionId] = useState('');

  // Inline editing
  const [editing, setEditing] = useState(false);
  const [editFields, setEditFields] = useState({});

  // PDF viewer
  const [showPdf, setShowPdf] = useState(false);

  // Enrichment
  const [enrichingPaper, setEnrichingPaper] = useState(false);
  const [doiInput, setDoiInput] = useState('');
  const [showDoiInput, setShowDoiInput] = useState(false);

  // Notes collapsible
  const [showNotes, setShowNotes] = useState(false);

  // Track which refs are being imported / were imported
  const [importingRef, setImportingRef] = useState(null); // index
  const [importingAll, setImportingAll] = useState(false);

  const decoded = decodeURIComponent(filename);

  useEffect(() => {
    Promise.all([
      fetchPaperDetail(decoded),
      fetchReferences(decoded).catch(() => ({ references: [] })),
      fetchCollections().catch(() => ({ collections: [] })),
    ]).then(([detail, refData, collData]) => {
      setPaper(detail);
      setNotes(detail.notes || '');
      setRead(detail.read ?? false);
      setRefs(refData.references || []);
      setCollections(collData.collections || []);
      setPaperCollections(detail.collections || []);
    }).catch(console.error)
      .finally(() => setLoading(false));
  }, [filename]);

  async function handleSaveNotes() {
    setSaving(true);
    try {
      await updateNotes(decoded, notes);
      toast.success('Notes saved');
    } catch (e) {
      toast.error('Failed to save notes');
    }
    setSaving(false);
  }

  async function handleToggleRead() {
    try {
      const res = await toggleRead(decoded);
      setRead(res.read);
      toast.info(res.read ? 'Marked as read' : 'Marked as unread');
    } catch (e) {
      toast.error('Failed to toggle read status');
    }
  }

  async function handleAddCollection() {
    if (!addCollectionId) return;
    try {
      await addPaperToCollection(Number(addCollectionId), decoded);
      const col = collections.find(c => c.id === Number(addCollectionId));
      setPaperCollections(prev => [...prev, { id: Number(addCollectionId), name: col?.name || '' }]);
      setAddCollectionId('');
      toast.success(`Added to ${col?.name || 'collection'}`);
    } catch (e) {
      toast.error('Failed to add to collection');
    }
  }

  async function handleRemoveCollection(colId) {
    try {
      await removePaperFromCollection(colId, decoded);
      setPaperCollections(prev => prev.filter(c => c.id !== colId));
      toast.info('Removed from collection');
    } catch (e) {
      toast.error('Failed to remove from collection');
    }
  }

  function startEditing() {
    setEditFields({
      title: paper.title || '',
      year: paper.year || '',
      journal: paper.journal || '',
      paper_type: paper.paper_type || '',
      chemistries: (paper.chemistries || []).join(', '),
      topics: (paper.topics || []).join(', '),
    });
    setEditing(true);
  }

  async function handleSaveMetadata() {
    const updates = {
      title: editFields.title,
      year: editFields.year ? Number(editFields.year) : null,
      journal: editFields.journal,
      paper_type: editFields.paper_type,
      chemistries: editFields.chemistries.split(',').map(s => s.trim()).filter(Boolean),
      topics: editFields.topics.split(',').map(s => s.trim()).filter(Boolean),
    };
    try {
      await updateMetadata(decoded, updates);
      setPaper(prev => ({ ...prev, ...updates }));
      setEditing(false);
      toast.success('Metadata updated');
    } catch (e) {
      toast.error('Failed to update metadata');
    }
  }

  async function handleImportRef(ref, index) {
    const doi = ref.DOI || ref.doi;
    if (!doi) {
      toast.error('No DOI available — cannot import');
      return;
    }
    setImportingRef(index);
    try {
      const res = await importMetadataOnly(doi);
      // Mark this ref as now in library
      setRefs(prev => prev.map((r, i) => i === index ? { ...r, in_library: true } : r));
      toast.success(`Added "${res.title || doi}" to library`);
    } catch (e) {
      toast.error(`Failed to import: ${e.message || 'Unknown error'}`);
    } finally {
      setImportingRef(null);
    }
  }

  async function handleImportAllRefs() {
    const importable = refs
      .map((r, i) => ({ ref: r, index: i }))
      .filter(({ ref }) => !ref.in_library && (ref.DOI || ref.doi));
    if (importable.length === 0) {
      toast.info('All references with DOIs are already in your library');
      return;
    }
    setImportingAll(true);
    let added = 0;
    let failed = 0;
    for (const { ref, index } of importable) {
      const doi = ref.DOI || ref.doi;
      try {
        await importMetadataOnly(doi);
        setRefs(prev => prev.map((r, i) => i === index ? { ...r, in_library: true } : r));
        added++;
      } catch {
        failed++;
      }
    }
    setImportingAll(false);
    if (added > 0) toast.success(`Added ${added} paper${added > 1 ? 's' : ''} to library`);
    if (failed > 0) toast.error(`Failed to import ${failed} reference${failed > 1 ? 's' : ''}`);
  }

  async function handleEnrichPaper() {
    setEnrichingPaper(true);
    try {
      const res = await enrichSinglePaper(decoded);
      if (res.success) {
        setPaper(res.paper);
        const fields = res.fields_updated || [];
        if (fields.length > 0) {
          toast.success(`Enriched: ${fields.join(', ')}`);
        } else {
          toast.info(res.doi ? 'Verified — no new metadata' : 'No updates available');
        }
        // Reload refs since enrichment may have added them
        fetchReferences(decoded).then(r => setRefs(r.references || [])).catch(() => {});
      } else {
        toast.error(res.error || 'Enrichment failed');
      }
    } catch (e) {
      toast.error('Enrichment failed: ' + e.message);
    } finally {
      setEnrichingPaper(false);
    }
  }

  async function handleEnrichWithDoi() {
    if (!doiInput.trim()) return;
    setEnrichingPaper(true);
    try {
      const res = await enrichFromCrossref(decoded, doiInput.trim());
      if (res.success) {
        setPaper(res.paper);
        setShowDoiInput(false);
        setDoiInput('');
        toast.success(`Re-enriched with DOI: ${res.doi}`);
        fetchReferences(decoded).then(r => setRefs(r.references || [])).catch(() => {});
      } else {
        toast.error(res.error || 'CrossRef lookup failed');
      }
    } catch (e) {
      toast.error('Enrichment failed: ' + e.message);
    } finally {
      setEnrichingPaper(false);
    }
  }

  if (loading) return <div className={styles.loading}>Loading paper…</div>;
  if (!paper) return <div className={styles.loading}>Paper not found.</div>;

  const allTags = [
    ...(paper.chemistries || []),
    ...(paper.topics || []),
    ...(paper.author_keywords || []),
  ];

  const availableCollections = collections.filter(
    c => !paperCollections.some(pc => pc.id === c.id)
  );

  return (
    <div className={styles.page}>
      <div className={styles.backLink} onClick={() => navigate(-1)}>
        <ArrowLeft size={16} /> Back
      </div>

      {/* Header — editable */}
      <div className={styles.header}>
        {editing ? (
          <div className={styles.editForm}>
            <input
              className={styles.editInput}
              value={editFields.title}
              onChange={e => setEditFields(f => ({ ...f, title: e.target.value }))}
              placeholder="Title"
            />
            <div className={styles.editRow}>
              <input
                className={styles.editInputSm}
                value={editFields.year}
                onChange={e => setEditFields(f => ({ ...f, year: e.target.value }))}
                placeholder="Year"
                type="number"
              />
              <input
                className={styles.editInputSm}
                value={editFields.journal}
                onChange={e => setEditFields(f => ({ ...f, journal: e.target.value }))}
                placeholder="Journal"
              />
              <input
                className={styles.editInputSm}
                value={editFields.paper_type}
                onChange={e => setEditFields(f => ({ ...f, paper_type: e.target.value }))}
                placeholder="Type"
              />
            </div>
            <div className={styles.editRow}>
              <input
                className={styles.editInputSm}
                value={editFields.chemistries}
                onChange={e => setEditFields(f => ({ ...f, chemistries: e.target.value }))}
                placeholder="Chemistries (comma separated)"
              />
              <input
                className={styles.editInputSm}
                value={editFields.topics}
                onChange={e => setEditFields(f => ({ ...f, topics: e.target.value }))}
                placeholder="Topics (comma separated)"
              />
            </div>
            <div className={styles.editActions}>
              <button className={styles.saveBtn} onClick={handleSaveMetadata}>
                <Save size={14} /> Save
              </button>
              <button className={styles.toggleBtn} onClick={() => setEditing(false)}>
                <XCircle size={14} /> Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className={styles.titleRow}>
              <h1 className={styles.title}>{paper.title || paper.filename}</h1>
              <button className={styles.editBtn} onClick={startEditing} title="Edit metadata">
                <Pencil size={14} />
              </button>
            </div>
            <div className={styles.meta}>
              {Array.isArray(paper.authors) && paper.authors.length > 0 && (
                <span className={styles.metaItem}>{paper.authors.join(', ')}</span>
              )}
              {typeof paper.authors === 'string' && paper.authors && (
                <span className={styles.metaItem}>{paper.authors}</span>
              )}
              {paper.year && (
                <span className={styles.metaItem}><Calendar size={14} /> {paper.year}</span>
              )}
              {paper.journal && (
                <span className={styles.metaItem}><BookOpen size={14} /> {paper.journal}</span>
              )}
              {paper.paper_type && (
                <span className={styles.metaItem}><FileText size={14} /> {paper.paper_type}</span>
              )}
            </div>
            {allTags.length > 0 && (
              <div className={styles.tags}>
                {allTags.map(t => <span key={t} className={styles.tag}>{t}</span>)}
              </div>
            )}
          </>
        )}
      </div>

      {/* Action bar — compact row with actions + collections */}
      <div className={styles.actionBar}>
        <div className={styles.actionBarLeft}>
          <button className={styles.actionBtn} onClick={handleToggleRead}>
            {read ? <><BookCheck size={14} /> Mark Unread</> : <><BookX size={14} /> Mark Read</>}
          </button>
          <button
            className={styles.actionBtn}
            onClick={handleEnrichPaper}
            disabled={enrichingPaper}
            title="Auto-enrich metadata from CrossRef / Semantic Scholar"
          >
            {enrichingPaper
              ? <><Loader size={14} className={styles.spinning} /> Enriching…</>
              : <><Zap size={14} /> Enrich</>}
          </button>
          <button
            className={styles.actionBtnSm}
            onClick={() => setShowDoiInput(!showDoiInput)}
            title="Provide a DOI to re-enrich from CrossRef"
          >
            <Pencil size={12} /> DOI
          </button>
          {paper.doi && (
            <a
              href={`https://doi.org/${paper.doi}`}
              target="_blank"
              rel="noreferrer"
              className={styles.doiLink}
            >
              DOI: {paper.doi}
            </a>
          )}
        </div>
        <div className={styles.actionBarRight}>
          {paperCollections.map(c => (
            <div key={c.id} className={styles.collectionChip}>
              <span>{c.name}</span>
              <button
                className={styles.chipRemove}
                onClick={() => handleRemoveCollection(c.id)}
                title="Remove from collection"
              >
                <X size={12} />
              </button>
            </div>
          ))}
          {availableCollections.length > 0 && (
            <div className={styles.addCollection}>
              <select
                className={styles.collectionSelect}
                value={addCollectionId}
                onChange={e => setAddCollectionId(e.target.value)}
              >
                <option value="">Add to collection…</option>
                {availableCollections.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <button
                className={styles.addColBtn}
                onClick={handleAddCollection}
                disabled={!addCollectionId}
              >
                <Plus size={14} />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* DOI input for manual enrichment */}
      {showDoiInput && (
        <div className={styles.doiInputBar}>
          <input
            className={styles.doiInputField}
            placeholder="Enter DOI (e.g. 10.1016/j.jpowsour.2024.235188)"
            value={doiInput}
            onChange={e => setDoiInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleEnrichWithDoi()}
          />
          <button className={styles.doiSubmitBtn} onClick={handleEnrichWithDoi} disabled={enrichingPaper || !doiInput.trim()}>
            {enrichingPaper ? <Loader size={14} className={styles.spinning} /> : <Check size={14} />}
            Enrich
          </button>
          <button className={styles.doiCancelBtn} onClick={() => { setShowDoiInput(false); setDoiInput(''); }}>
            <X size={14} />
          </button>
        </div>
      )}

      {/* Full-width content */}
      <div className={styles.content}>
        {/* PDF Viewer */}
        {paper.has_pdf && (
          <div className={styles.card}>
            <div className={styles.cardTitle} style={{ cursor: 'pointer' }} onClick={() => setShowPdf(v => !v)}>
              <FileText size={16} /> PDF Viewer
              <span style={{ marginLeft: 'auto', fontSize: 'var(--astro-text-xs)', color: 'var(--astro-text-muted)' }}>
                {showPdf ? 'Click to collapse' : 'Click to expand'}
              </span>
            </div>
            {showPdf && (
              <div className={styles.pdfContainer}>
                <object
                  data={`${getPdfUrl(decoded)}#toolbar=1&navpanes=0`}
                  type="application/pdf"
                  className={styles.pdfFrame}
                >
                  <p style={{ padding: '1rem', textAlign: 'center' }}>
                    PDF cannot be displayed inline.{' '}
                    <a href={getPdfUrl(decoded)} target="_blank" rel="noreferrer">Open PDF</a>
                  </p>
                </object>
              </div>
            )}
          </div>
        )}

        {/* Abstract */}
        {paper.abstract && (
          <div className={styles.card}>
            <div className={styles.cardTitle}><FileText size={16} /> Abstract</div>
            <div className={styles.abstract} style={{ whiteSpace: 'pre-line' }}>{cleanAbstract(paper.abstract)}</div>
          </div>
        )}

        {/* AI Summary */}
        {paper.ai_summary && (
          <div className={styles.card}>
            <div className={styles.cardTitle}><Sparkles size={16} /> AI Summary</div>
            <div className={styles.summary}>{paper.ai_summary}</div>
          </div>
        )}

        {/* References */}
        {refs.length > 0 && (
          <div className={styles.card}>
            <div className={styles.refHeader}>
              <div className={styles.cardTitle} style={{ marginBottom: 0 }}>References ({refs.length})</div>
              {refs.some(r => !r.in_library && (r.DOI || r.doi)) && (
                <button
                  className={styles.addAllBtn}
                  onClick={handleImportAllRefs}
                  disabled={importingAll}
                >
                  {importingAll
                    ? <><Loader size={13} className={styles.spin} /> Importing…</>
                    : <><Download size={13} /> Add All to Library</>}
                </button>
              )}
            </div>
            <ol className={styles.refList}>
              {refs.slice(0, 50).map((r, i) => (
                <li key={i} className={r.in_library ? styles.refInLibrary : ''}>
                  <span className={styles.refNumber}>[{i + 1}]</span>
                  <div className={styles.refContent}>
                    <RefCitation r={r} />
                    {r.DOI ? (
                      <a
                        href={`https://doi.org/${r.DOI}`}
                        target="_blank"
                        rel="noreferrer"
                        className={styles.refDoi}
                      >
                        {r.DOI}
                      </a>
                    ) : (r['article-title'] || r['volume-title']) ? (
                      <a
                        href={`https://scholar.google.com/scholar?q=${encodeURIComponent(r['article-title'] || r['volume-title'])}`}
                        target="_blank"
                        rel="noreferrer"
                        className={styles.refDoi}
                        title="Search on Google Scholar"
                      >
                        <ExternalLink size={11} /> Scholar
                      </a>
                    ) : null}
                  </div>
                  <div className={styles.refActions}>
                    {r.in_library ? (
                      <span className={styles.inLibraryBadge}>
                        <Check size={12} /> In Library
                      </span>
                    ) : (r.DOI || r.doi) ? (
                      <button
                        className={styles.addRefBtn}
                        onClick={() => handleImportRef(r, i)}
                        disabled={importingRef === i || importingAll}
                        title="Add to library (metadata only)"
                      >
                        {importingRef === i
                          ? <><Loader size={12} className={styles.spin} /> Adding…</>
                          : <><Download size={12} /> Add to Library</>}
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        )}

        {/* Notes — collapsible */}
        <div className={styles.card}>
          <div
            className={styles.cardTitle}
            style={{ cursor: 'pointer', userSelect: 'none' }}
            onClick={() => setShowNotes(v => !v)}
          >
            <StickyNote size={16} /> Notes
            <span style={{ marginLeft: 'auto', fontSize: 'var(--astro-text-xs)', color: 'var(--astro-text-muted)' }}>
              {showNotes ? 'Click to collapse' : 'Click to expand'}
            </span>
          </div>
          {showNotes && (
            <>
              <textarea
                className={styles.notesArea}
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="Add your notes here…"
              />
              <button className={styles.saveBtn} onClick={handleSaveNotes} disabled={saving}>
                {saving ? 'Saving…' : 'Save Notes'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
