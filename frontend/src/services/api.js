/**
 * API client — all fetch calls to the FastAPI backend.
 * Centralizes error handling and base URL configuration.
 */

const BASE = '/api';

async function request(path, options = {}) {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Papers ──────────────────────────────────────────────
export function fetchPapers(params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v != null && v !== '') qs.set(k, v);
  });
  const query = qs.toString();
  return request(`/papers${query ? '?' + query : ''}`);
}

export function fetchPaperDetail(filename) {
  return request(`/papers/${encodeURIComponent(filename)}`);
}

export function fetchPaperStats() {
  return request('/papers/stats');
}

export function fetchChartData() {
  return request('/papers/stats/charts');
}

export function fetchFilters() {
  return request('/papers/filters');
}

export function fetchReferences(filename) {
  return request(`/papers/${encodeURIComponent(filename)}/references`);
}

export function updateNotes(filename, content) {
  return request(`/papers/${encodeURIComponent(filename)}/notes`, {
    method: 'PUT',
    body: JSON.stringify({ content }),
  });
}

export function toggleRead(filename) {
  return request(`/papers/${encodeURIComponent(filename)}/read/toggle`, {
    method: 'POST',
  });
}

export function deletePapers(filenames) {
  return request('/papers', {
    method: 'DELETE',
    body: JSON.stringify({ filenames }),
  });
}

export function updateMetadata(filename, updates) {
  return request(`/papers/${encodeURIComponent(filename)}/metadata`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

export function getPdfUrl(filename) {
  return `${BASE}/papers/${encodeURIComponent(filename)}/pdf`;
}

// ── Search / RAG ────────────────────────────────────────
export function searchChunks(query, opts = {}) {
  return request('/search/chunks', {
    method: 'POST',
    body: JSON.stringify({ query, ...opts }),
  });
}

export function askQuestion(question, opts = {}) {
  return request('/search/ask', {
    method: 'POST',
    body: JSON.stringify({ question, ...opts }),
  });
}

// ── Collections ─────────────────────────────────────────
export function fetchCollections() {
  return request('/collections');
}

export function createCollection(data) {
  return request('/collections', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function fetchCollectionPapers(collectionId) {
  return request(`/collections/${collectionId}/papers`);
}

export function addPaperToCollection(collectionId, filename) {
  return request(`/collections/${collectionId}/papers`, {
    method: 'POST',
    body: JSON.stringify({ filename }),
  });
}

export function addPapersToCollectionBulk(collectionId, filenames) {
  return request(`/collections/${collectionId}/papers/bulk`, {
    method: 'POST',
    body: JSON.stringify({ filenames }),
  });
}

export function fetchMatchingFilenames(params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v != null && v !== '') qs.set(k, v);
  });
  const query = qs.toString();
  return request(`/papers/filenames${query ? '?' + query : ''}`);
}

export function removePaperFromCollection(collectionId, filename) {
  return request(`/collections/${collectionId}/papers/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  });
}

export function deleteCollection(id) {
  return request(`/collections/${id}`, { method: 'DELETE' });
}

export function updateCollection(id, data) {
  return request(`/collections/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

// ── History ─────────────────────────────────────────────
export function fetchHistory(params = {}) {
  const qs = new URLSearchParams();
  if (params.limit) qs.set('limit', params.limit);
  if (params.starred_only) qs.set('starred_only', 'true');
  const query = qs.toString();
  return request(`/history${query ? '?' + query : ''}`);
}

export function toggleStar(queryId) {
  return request(`/history/${queryId}/star`, { method: 'POST' });
}

export function deleteQuery(queryId) {
  return request(`/history/${queryId}`, { method: 'DELETE' });
}

export function clearHistory() {
  return request('/history', { method: 'DELETE' });
}

// ── Settings ────────────────────────────────────────────
export function fetchSettings() {
  return request('/settings');
}

export function updateSettings(updates) {
  return request('/settings', {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

export function fetchBackups() {
  return request('/settings/backups');
}

export function createBackup() {
  return request('/settings/backups', { method: 'POST' });
}

// ── Import ──────────────────────────────────────────────
export function importFromUrl(url) {
  return request('/import/url', {
    method: 'POST',
    body: JSON.stringify({ url }),
  });
}

export function importByDoi(doi) {
  return request('/import/doi', {
    method: 'POST',
    body: JSON.stringify({ doi }),
  });
}

export async function uploadPdf(file) {
  const formData = new FormData();
  formData.append('files', file);
  const res = await fetch(`${BASE}/import/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

export function importMetadataOnly(doi, title) {
  return request('/import/metadata-only', {
    method: 'POST',
    body: JSON.stringify({ doi, title }),
  });
}

export function enrichPapers(filenames, maxPapers) {
  const body = {};
  if (filenames) body.filenames = filenames;
  if (maxPapers) body.max_papers = maxPapers;
  return request('/import/enrich', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function importBulkDois(dois) {
  return request('/import/bulk-doi', {
    method: 'POST',
    body: JSON.stringify({ dois }),
  });
}

export function fetchImportLogs() {
  return request('/import/logs');
}

// ── Trash ───────────────────────────────────────────────
export function fetchTrash() {
  return request('/papers/trash');
}

export function restorePapers(filenames) {
  return request('/papers/trash/restore', {
    method: 'POST',
    body: JSON.stringify({ filenames }),
  });
}

export function emptyTrash() {
  return request('/papers/trash', { method: 'DELETE' });
}

export function hardDeletePaper(filename) {
  return request(`/papers/trash/${encodeURIComponent(filename)}`, { method: 'DELETE' });
}

// ── Discover ────────────────────────────────────────────
export function discoverSearch(query, limit = 20, sort = 'relevance') {
  return request('/discover/search', {
    method: 'POST',
    body: JSON.stringify({ query, limit, sort }),
  });
}

export function fetchGaps(limit = 20) {
  return request(`/discover/gaps?limit=${limit}`);
}

export function addDiscoverPaper(data) {
  return request('/discover/add', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
