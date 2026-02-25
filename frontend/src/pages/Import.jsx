import { useState, useRef, useEffect } from 'react';
import { Link2, Hash, Upload, Loader, List, FileText, CheckCircle, XCircle, Plus } from 'lucide-react';
import {
  importFromUrl, importByDoi, uploadPdf,
  importMetadataOnly, importBulkDois, fetchImportLogs,
} from '../services/api';
import { useToast } from '../components/Toast';

const TABS = [
  { key: 'url', label: 'URL', icon: Link2 },
  { key: 'doi', label: 'DOI', icon: Hash },
  { key: 'bulk', label: 'Bulk DOI', icon: List },
  { key: 'pdf', label: 'PDF Upload', icon: Upload },
  { key: 'logs', label: 'Import Log', icon: FileText },
];

export default function Import() {
  const [tab, setTab] = useState('url');
  const [url, setUrl] = useState('');
  const [doi, setDoi] = useState('');
  const [bulkDois, setBulkDois] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);
  const toast = useToast();

  useEffect(() => {
    if (tab === 'logs') loadLogs();
  }, [tab]);

  async function loadLogs() {
    setLogsLoading(true);
    try {
      const data = await fetchImportLogs();
      setLogs(data.logs || []);
    } catch (e) { console.error(e); }
    setLogsLoading(false);
  }

  async function handleUrlImport(e) {
    e.preventDefault();
    if (!url.trim() || loading) return;
    setLoading(true);
    setResults(null);
    try {
      const res = await importFromUrl(url.trim());
      if (res.success) {
        toast.success(`Imported: ${res.title || res.filename || 'paper'}`);
        setResults({ type: 'success', message: `Imported: ${res.title || res.filename}`, details: res });
        setUrl('');
      } else {
        toast.error(res.error || 'Import failed');
        setResults({ type: 'error', message: res.error || 'Import failed' });
      }
    } catch (err) {
      toast.error(err.message);
      setResults({ type: 'error', message: err.message });
    }
    setLoading(false);
  }

  async function handleDoiImport(e) {
    e.preventDefault();
    if (!doi.trim() || loading) return;
    setLoading(true);
    setResults(null);
    try {
      const res = await importByDoi(doi.trim());
      if (res.success) {
        toast.success(`Imported: ${res.title || res.filename || 'paper'}`);
        setResults({ type: 'success', message: `Imported: ${res.title || res.filename}`, details: res });
        setDoi('');
      } else {
        toast.error(res.error || 'Import failed');
        setResults({ type: 'error', message: res.error || 'Import failed' });
      }
    } catch (err) {
      toast.error(err.message);
      setResults({ type: 'error', message: err.message });
    }
    setLoading(false);
  }

  async function handleBulkImport(e) {
    e.preventDefault();
    const dois = bulkDois.split('\n').map(d => d.trim()).filter(d => d && d.startsWith('10.'));
    if (dois.length === 0 || loading) return;
    setLoading(true);
    setResults(null);
    try {
      const res = await importBulkDois(dois);
      toast.success(`Imported ${res.succeeded}/${res.total} papers`);
      setResults({
        type: 'bulk',
        message: `${res.succeeded} succeeded, ${res.total - res.succeeded} failed`,
        items: res.results,
      });
      if (res.succeeded === res.total) setBulkDois('');
    } catch (err) {
      toast.error(err.message);
      setResults({ type: 'error', message: err.message });
    }
    setLoading(false);
  }

  async function handleFiles(fileList) {
    if (!fileList || fileList.length === 0 || loading) return;
    setLoading(true);
    setResults(null);
    const items = [];
    for (const file of fileList) {
      try {
        const res = await uploadPdf(file);
        const r = res.results?.[0] || res;
        if (r.success !== false) {
          items.push({ name: file.name, success: true, title: r.title || r.filename || file.name });
        } else {
          items.push({ name: file.name, success: false, error: r.error || 'Upload failed' });
        }
      } catch (err) {
        items.push({ name: file.name, success: false, error: err.message });
      }
    }
    const succeeded = items.filter(i => i.success).length;
    toast.success(`Uploaded ${succeeded}/${items.length} files`);
    setResults({ type: 'bulk', message: `${succeeded}/${items.length} uploaded`, items });
    setLoading(false);
    if (fileRef.current) fileRef.current.value = '';
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const files = [...e.dataTransfer.files].filter(f => f.name.endsWith('.pdf'));
    handleFiles(files);
  }

  function handleFileInput(e) {
    handleFiles([...e.target.files]);
  }

  const inputStyle = {
    width: '100%', padding: '10px 14px',
    background: 'var(--astro-bg)', border: '1px solid var(--astro-border)',
    borderRadius: 'var(--astro-radius)', color: 'var(--astro-text)',
    fontSize: 'var(--astro-text-sm)', outline: 'none', boxSizing: 'border-box',
  };

  const hintStyle = {
    fontSize: 'var(--astro-text-xs)', color: 'var(--astro-text-muted)', marginTop: 6,
  };

  const btnStyle = {
    marginTop: 12, padding: '10px 20px', background: 'var(--astro-primary)',
    border: 'none', borderRadius: 'var(--astro-radius)', color: '#fff',
    fontSize: 'var(--astro-text-sm)', cursor: 'pointer',
    display: 'inline-flex', alignItems: 'center', gap: 6,
    opacity: loading ? 0.6 : 1,
  };

  return (
    <div>
      {/* Header */}
      <h1 style={{ fontSize: 'var(--astro-text-2xl)', fontWeight: 700, marginBottom: 24, display: 'flex', alignItems: 'center', gap: 10 }}>
        <Plus size={24} /> Import Papers
      </h1>

      {/* Tabs */}
      <div style={{
        display: 'flex', gap: 4, marginBottom: 24,
        borderBottom: '1px solid var(--astro-border)', paddingBottom: 0,
      }}>
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key); setResults(null); }}
            style={{
              padding: '10px 18px', background: 'transparent',
              border: 'none', borderBottom: tab === t.key ? '2px solid var(--astro-primary)' : '2px solid transparent',
              color: tab === t.key ? 'var(--astro-primary)' : 'var(--astro-text-muted)',
              fontSize: 'var(--astro-text-sm)', fontWeight: tab === t.key ? 600 : 400,
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
              transition: 'all 0.15s',
            }}
          >
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{
        background: 'var(--astro-surface)', border: '1px solid var(--astro-border)',
        borderRadius: 'var(--astro-radius)', padding: 24, maxWidth: 700,
      }}>

        {/* URL Import */}
        {tab === 'url' && (
          <form onSubmit={handleUrlImport}>
            <label style={{ fontWeight: 500, fontSize: 'var(--astro-text-sm)', marginBottom: 8, display: 'block' }}>
              Publisher or arXiv URL
            </label>
            <input
              style={inputStyle}
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://doi.org/10.1234/... or https://arxiv.org/abs/..."
              disabled={loading}
            />
            <p style={hintStyle}>
              Supports DOI links, arXiv, ACS, Wiley, Springer, Nature, direct PDF URLs, and more.
            </p>
            <button style={btnStyle} type="submit" disabled={loading || !url.trim()}>
              {loading ? <><Loader size={14} style={{ animation: 'spin 1s linear infinite' }} /> Importing…</> : <><Link2 size={14} /> Import from URL</>}
            </button>
          </form>
        )}

        {/* DOI Import */}
        {tab === 'doi' && (
          <form onSubmit={handleDoiImport}>
            <label style={{ fontWeight: 500, fontSize: 'var(--astro-text-sm)', marginBottom: 8, display: 'block' }}>
              Single DOI
            </label>
            <input
              style={inputStyle}
              value={doi}
              onChange={e => setDoi(e.target.value)}
              placeholder="10.1234/example.2024"
              disabled={loading}
            />
            <p style={hintStyle}>
              Enter a DOI to fetch metadata and PDF from CrossRef & Semantic Scholar.
            </p>
            <button style={btnStyle} type="submit" disabled={loading || !doi.trim()}>
              {loading ? <><Loader size={14} style={{ animation: 'spin 1s linear infinite' }} /> Importing…</> : <><Hash size={14} /> Import by DOI</>}
            </button>
          </form>
        )}

        {/* Bulk DOI Import */}
        {tab === 'bulk' && (
          <form onSubmit={handleBulkImport}>
            <label style={{ fontWeight: 500, fontSize: 'var(--astro-text-sm)', marginBottom: 8, display: 'block' }}>
              Bulk DOI Import
            </label>
            <textarea
              style={{ ...inputStyle, minHeight: 180, resize: 'vertical', fontFamily: 'monospace' }}
              value={bulkDois}
              onChange={e => setBulkDois(e.target.value)}
              placeholder={"10.1016/j.jpowsour.2022.231127\n10.1038/s41467-024-49868-9\n10.1039/d0ee01074j"}
              disabled={loading}
            />
            <p style={hintStyle}>
              One DOI per line. Lines not starting with "10." are ignored.
              {bulkDois && (
                <span style={{ marginLeft: 8, color: 'var(--astro-primary)' }}>
                  ({bulkDois.split('\n').filter(d => d.trim().startsWith('10.')).length} DOIs detected)
                </span>
              )}
            </p>
            <button style={btnStyle} type="submit"
              disabled={loading || bulkDois.split('\n').filter(d => d.trim().startsWith('10.')).length === 0}
            >
              {loading
                ? <><Loader size={14} style={{ animation: 'spin 1s linear infinite' }} /> Importing…</>
                : <><List size={14} /> Import {bulkDois.split('\n').filter(d => d.trim().startsWith('10.')).length} DOIs</>
              }
            </button>
          </form>
        )}

        {/* PDF Upload */}
        {tab === 'pdf' && (
          <div>
            <label style={{ fontWeight: 500, fontSize: 'var(--astro-text-sm)', marginBottom: 8, display: 'block' }}>
              Upload PDF files
            </label>
            <div
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileRef.current?.click()}
              style={{
                border: `2px dashed ${dragOver ? 'var(--astro-primary)' : 'var(--astro-border)'}`,
                borderRadius: 'var(--astro-radius)',
                padding: '40px 20px',
                textAlign: 'center',
                cursor: 'pointer',
                transition: 'border-color 0.2s, background 0.2s',
                background: dragOver ? 'rgba(99,102,241,0.05)' : 'transparent',
              }}
            >
              <Upload size={36} style={{ color: 'var(--astro-text-muted)', marginBottom: 8 }} />
              <div style={{ fontSize: 'var(--astro-text-sm)', fontWeight: 500 }}>
                Click to select files or drag and drop
              </div>
              <div style={{ fontSize: 'var(--astro-text-xs)', color: 'var(--astro-text-muted)', marginTop: 4 }}>
                Supports multiple PDFs at once
              </div>
            </div>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf"
              multiple
              style={{ display: 'none' }}
              onChange={handleFileInput}
              disabled={loading}
            />
            {loading && (
              <div style={{
                marginTop: 12, display: 'flex', alignItems: 'center', gap: 8,
                fontSize: 'var(--astro-text-sm)', color: 'var(--astro-text-muted)',
              }}>
                <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} /> Uploading…
              </div>
            )}
          </div>
        )}

        {/* Import Logs */}
        {tab === 'logs' && (
          <div>
            <div style={{ fontWeight: 500, fontSize: 'var(--astro-text-sm)', marginBottom: 12 }}>
              Import History
            </div>
            {logsLoading ? (
              <div style={{ color: 'var(--astro-text-muted)', fontSize: 'var(--astro-text-sm)' }}>Loading…</div>
            ) : logs.length === 0 ? (
              <div style={{ color: 'var(--astro-text-muted)', fontSize: 'var(--astro-text-sm)', padding: 20, textAlign: 'center' }}>
                No import logs found.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {logs.map((log, i) => (
                  <div
                    key={i}
                    style={{
                      background: 'var(--astro-bg)', border: '1px solid var(--astro-border)',
                      borderRadius: 'var(--astro-radius)', padding: '10px 14px',
                      fontSize: 'var(--astro-text-sm)',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 500 }}>{log.source || log.filename}</span>
                      <span style={{ color: 'var(--astro-text-muted)', fontSize: 'var(--astro-text-xs)' }}>
                        {log.timestamp}
                      </span>
                    </div>
                    <div style={{ color: 'var(--astro-text-muted)', fontSize: 'var(--astro-text-xs)', marginTop: 4 }}>
                      {log.papers_added != null && <span style={{ color: 'var(--astro-success)' }}>+{log.papers_added} added</span>}
                      {log.papers_skipped > 0 && <span style={{ marginLeft: 8 }}>{log.papers_skipped} skipped</span>}
                      {log.errors > 0 && <span style={{ marginLeft: 8, color: 'var(--astro-danger)' }}>{log.errors} errors</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Results feedback */}
        {results && tab !== 'logs' && (
          <div style={{
            marginTop: 20, padding: '12px 16px',
            background: results.type === 'error' ? 'rgba(239,68,68,0.08)' : 'rgba(34,197,94,0.08)',
            borderRadius: 'var(--astro-radius)',
            border: `1px solid ${results.type === 'error' ? 'rgba(239,68,68,0.2)' : 'rgba(34,197,94,0.2)'}`,
            fontSize: 'var(--astro-text-sm)',
          }}>
            <div style={{ fontWeight: 500, marginBottom: results.items ? 8 : 0, display: 'flex', alignItems: 'center', gap: 6 }}>
              {results.type === 'error'
                ? <><XCircle size={14} style={{ color: 'var(--astro-danger)' }} /> {results.message}</>
                : <><CheckCircle size={14} style={{ color: 'var(--astro-success)' }} /> {results.message}</>
              }
            </div>
            {results.items && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 200, overflowY: 'auto' }}>
                {results.items.map((item, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 'var(--astro-text-xs)' }}>
                    {item.success
                      ? <CheckCircle size={12} style={{ color: 'var(--astro-success)', flexShrink: 0 }} />
                      : <XCircle size={12} style={{ color: 'var(--astro-danger)', flexShrink: 0 }} />
                    }
                    <span>{item.doi || item.name || item.title}</span>
                    {item.title && <span style={{ color: 'var(--astro-text-muted)' }}>— {item.title}</span>}
                    {item.error && <span style={{ color: 'var(--astro-danger)' }}>— {item.error}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
