import { useState, useRef } from 'react';
import { X, Link2, Hash, Upload, Loader } from 'lucide-react';
import { importFromUrl, importByDoi, uploadPdf } from '../services/api';
import { useToast } from './Toast';
import styles from './ImportModal.module.css';

const TABS = [
  { key: 'url', label: 'URL', icon: Link2 },
  { key: 'doi', label: 'DOI', icon: Hash },
  { key: 'pdf', label: 'PDF Upload', icon: Upload },
];

export default function ImportModal({ open, onClose, onImported }) {
  const [tab, setTab] = useState('url');
  const [url, setUrl] = useState('');
  const [doi, setDoi] = useState('');
  const [loading, setLoading] = useState(false);
  const fileRef = useRef(null);
  const toast = useToast();

  if (!open) return null;

  async function handleUrlImport(e) {
    e.preventDefault();
    if (!url.trim() || loading) return;
    setLoading(true);
    try {
      const res = await importFromUrl(url.trim());
      if (res.success) {
        toast.success(`Imported: ${res.title || res.filename || 'paper'}`);
        setUrl('');
        onImported?.();
      } else {
        toast.error(res.error || 'Import failed');
      }
    } catch (err) {
      toast.error(err.message);
    }
    setLoading(false);
  }

  async function handleDoiImport(e) {
    e.preventDefault();
    if (!doi.trim() || loading) return;
    setLoading(true);
    try {
      const res = await importByDoi(doi.trim());
      if (res.success) {
        toast.success(`Imported: ${res.title || res.filename || 'paper'}`);
        setDoi('');
        onImported?.();
      } else {
        toast.error(res.error || 'Import failed');
      }
    } catch (err) {
      toast.error(err.message);
    }
    setLoading(false);
  }

  async function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file || loading) return;
    setLoading(true);
    try {
      const res = await uploadPdf(file);
      if (res.results?.length > 0) {
        const r = res.results[0];
        if (r.success) {
          toast.success(`Uploaded: ${r.title || r.filename || file.name}`);
          onImported?.();
        } else {
          toast.error(r.error || 'Upload failed');
        }
      } else if (res.success) {
        toast.success('PDF uploaded successfully');
        onImported?.();
      } else {
        toast.error(res.error || 'Upload failed');
      }
    } catch (err) {
      toast.error(err.message);
    }
    setLoading(false);
    if (fileRef.current) fileRef.current.value = '';
  }

  function handleOverlayClick(e) {
    if (e.target === e.currentTarget) onClose();
  }

  return (
    <div className={styles.overlay} onClick={handleOverlayClick}>
      <div className={styles.modal}>
        <div className={styles.modalHeader}>
          <h2 className={styles.modalTitle}>Import Paper</h2>
          <button className={styles.closeBtn} onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Tabs */}
        <div className={styles.tabs}>
          {TABS.map(t => (
            <button
              key={t.key}
              className={`${styles.tab} ${tab === t.key ? styles.tabActive : ''}`}
              onClick={() => setTab(t.key)}
            >
              <t.icon size={14} /> {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className={styles.tabContent}>
          {tab === 'url' && (
            <form onSubmit={handleUrlImport}>
              <label className={styles.label}>Publisher or arXiv URL</label>
              <input
                className={styles.input}
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://doi.org/10.1234/... or https://arxiv.org/abs/..."
                disabled={loading}
              />
              <p className={styles.hint}>
                Supports DOI links, arXiv, ACS, Wiley, Springer, Nature, etc.
              </p>
              <button className={styles.submitBtn} type="submit" disabled={loading || !url.trim()}>
                {loading ? <><Loader size={14} className={styles.spin} /> Importing…</> : 'Import from URL'}
              </button>
            </form>
          )}

          {tab === 'doi' && (
            <form onSubmit={handleDoiImport}>
              <label className={styles.label}>DOI</label>
              <input
                className={styles.input}
                value={doi}
                onChange={e => setDoi(e.target.value)}
                placeholder="10.1234/example.2024"
                disabled={loading}
              />
              <p className={styles.hint}>
                Enter a DOI to fetch metadata from CrossRef & Semantic Scholar.
              </p>
              <button className={styles.submitBtn} type="submit" disabled={loading || !doi.trim()}>
                {loading ? <><Loader size={14} className={styles.spin} /> Importing…</> : 'Import by DOI'}
              </button>
            </form>
          )}

          {tab === 'pdf' && (
            <div>
              <label className={styles.label}>Upload a PDF file</label>
              <div
                className={styles.dropzone}
                onClick={() => fileRef.current?.click()}
              >
                <Upload size={32} className={styles.dropzoneIcon} />
                <span>Click to select a PDF file</span>
                <span className={styles.hint}>or drag and drop</span>
              </div>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf"
                style={{ display: 'none' }}
                onChange={handleFileUpload}
                disabled={loading}
              />
              {loading && (
                <div className={styles.uploadProgress}>
                  <Loader size={14} className={styles.spin} /> Uploading…
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
