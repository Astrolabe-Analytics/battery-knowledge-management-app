"""
Import API routes — URL/DOI import, PDF upload, enrichment.

Re-implements the Streamlit-heavy process_url_import and process_uploaded_pdfs
as API-friendly functions (no st.* calls).
"""
import re
import sys
import json
import time
import subprocess
import urllib.parse
from pathlib import Path
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class URLImportRequest(BaseModel):
    url: str

class DOIImportRequest(BaseModel):
    doi: str

class MetadataOnlyImportRequest(BaseModel):
    doi: str
    title: Optional[str] = None

class EnrichRequest(BaseModel):
    filenames: list[str] | None = None
    max_papers: int | None = None

class BulkDOIRequest(BaseModel):
    dois: list[str]

class ImportResult(BaseModel):
    success: bool
    filename: str | None = None
    title: str | None = None
    error: str | None = None
    metadata_only: bool = False
    steps: list[str] = []


# ---------------------------------------------------------------------------
# Internal helpers (Streamlit-free re-implementations)
# ---------------------------------------------------------------------------

def _extract_doi_from_url(url: str) -> Optional[str]:
    """Extract DOI from a publisher URL."""
    doi_match = re.search(r'(?:doi\.org/|/doi/(?:abs/|full/)?)(10\.\d+/[^\s?&#]+)', url)
    if doi_match:
        return doi_match.group(1)
    return None


def _scrape_doi_from_page(url: str) -> Optional[str]:
    """Scrape a publisher page to find DOI in meta tags or JSON-LD."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    try:
        resp = requests.get(url, timeout=15, headers=headers)
        if resp.status_code == 403:
            return None
        if resp.status_code != 200:
            return None

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Try meta tags
        for attr, val in [
            ('name', 'citation_doi'), ('name', 'DC.Identifier'),
            ('property', 'citation_doi'), ('name', 'DOI'),
            ('name', 'dc.identifier'), ('name', 'prism.doi'),
        ]:
            tag = soup.find('meta', {attr: val})
            if tag and tag.get('content'):
                content = tag['content'].strip()
                if 'doi.org/' in content:
                    return content.split('doi.org/')[-1]
                if content.startswith('10.'):
                    return content

        # Try JSON-LD
        for script in soup.find_all('script', {'type': 'application/ld+json'}):
            m = re.search(r'"doi"\s*:\s*"(10\.\d+/[^"]+)"', script.string or '')
            if m:
                return m.group(1)

        # Last resort: regex on page text
        m = re.search(r'\b(10\.\d{4,}/[^\s<>"\']+)\b', resp.text)
        if m:
            candidate = re.sub(r'[,;.\)]+$', '', m.group(1))
            if candidate:
                return candidate
    except Exception:
        pass
    return None


def _query_crossref(doi: str) -> Optional[dict]:
    """Query CrossRef for metadata (Streamlit-free version)."""
    try:
        url = f"https://api.crossref.org/works/{doi}"
        headers = {'User-Agent': 'AstrolabeLibrary/1.0 (mailto:researcher@example.com)'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        message = resp.json().get('message', {})

        metadata = {}
        titles = message.get('title', [])
        if titles:
            metadata['title'] = titles[0]

        authors = []
        for a in message.get('author', []):
            given, family = a.get('given', ''), a.get('family', '')
            if family:
                authors.append(f"{family}, {given}" if given else family)
        metadata['authors'] = authors[:10]

        published = message.get('published-print') or message.get('published-online')
        if published and 'date-parts' in published:
            parts = published['date-parts'][0]
            if parts:
                metadata['year'] = str(parts[0])

        metadata['journal'] = message.get('container-title', [''])[0] if message.get('container-title') else ''
        metadata['abstract'] = message.get('abstract', '')
        metadata['volume'] = message.get('volume', '')
        metadata['issue'] = message.get('issue', '')
        metadata['pages'] = message.get('page', '')

        # References
        refs = []
        for ref in message.get('reference', [])[:100]:
            refs.append({
                'title': ref.get('article-title', ref.get('unstructured', '')),
                'doi': ref.get('DOI', ''),
                'year': ref.get('year', ''),
                'authors': ref.get('author', ''),
            })
        metadata['references'] = refs

        # Author keywords
        metadata['author_keywords'] = []

        return metadata
    except Exception:
        return None


def _find_open_access_pdf(doi: str) -> Optional[str]:
    """Check Unpaywall for an open-access PDF URL."""
    try:
        url = f"https://api.unpaywall.org/v2/{doi}?email=researcher@example.com"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('is_oa') and data.get('best_oa_location'):
                return data['best_oa_location'].get('url_for_pdf')
    except Exception:
        pass
    return None


def _run_ingestion_pipeline():
    """Run the 4-stage ingestion pipeline as a subprocess."""
    for stage in ["parse", "chunk", "metadata", "embed"]:
        flag = "--new-only" if stage != "embed" else ""
        cmd = [sys.executable, "scripts/ingest_pipeline.py", "--stage", stage]
        if flag:
            cmd.append(flag)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Pipeline stage '{stage}' failed: {result.stderr or result.stdout}")


def _save_metadata_only_paper(doi: str, crossref_metadata: dict) -> str:
    """Save a metadata-only paper (no PDF). Streamlit-free version."""
    from lib.library_operations import save_metadata_only_paper
    return save_metadata_only_paper(doi, crossref_metadata)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/url")
def import_from_url(body: URLImportRequest):
    """
    Import a paper from URL (arXiv, DOI, publisher page, or direct PDF link).
    Re-implements process_url_import without Streamlit dependencies.
    """
    url = body.url.strip()
    papers_dir = Path("papers")
    papers_dir.mkdir(parents=True, exist_ok=True)
    steps: list[str] = []
    result = {"success": False, "filename": None, "title": None, "error": None, "metadata_only": False, "steps": steps}

    try:
        # --- arXiv ---
        if 'arxiv.org' in url:
            steps.append("Detected arXiv paper")
            arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', url)
            if not arxiv_match:
                result["error"] = "Invalid arXiv URL format"
                return result

            arxiv_id = arxiv_match.group(1)
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            filename = f"arxiv_{arxiv_id.replace('.', '_')}.pdf"
            steps.append(f"Downloading arXiv ID {arxiv_id}")

            resp = requests.get(pdf_url, timeout=30)
            if resp.status_code == 200:
                (papers_dir / filename).write_bytes(resp.content)
                result["filename"] = filename
                result["success"] = True
                steps.append(f"Downloaded {filename}")
            else:
                result["error"] = f"arXiv download failed (HTTP {resp.status_code})"
                return result

        # --- Publisher page ---
        elif any(pub in url.lower() for pub in [
            'sciencedirect.com', 'ieeexplore.ieee.org', 'onlinelibrary.wiley.com',
            'link.springer.com', 'nature.com/articles', 'mdpi.com', 'cell.com',
            'thelancet.com', 'pubs.acs.org', 'pubs.rsc.org', 'iopscience.iop.org',
        ]):
            steps.append("Detected publisher article page")
            doi = _extract_doi_from_url(url) or _scrape_doi_from_page(url)
            if not doi:
                result["error"] = "Could not extract DOI from publisher page"
                return result
            steps.append(f"Found DOI: {doi}")

            metadata = _query_crossref(doi)
            if not metadata:
                result["error"] = "CrossRef metadata lookup failed"
                return result
            result["title"] = metadata.get("title", "Unknown")
            steps.append(f"Found: {result['title']}")

            pdf_url = _find_open_access_pdf(doi)
            if pdf_url:
                steps.append("Found open access PDF")
                try:
                    pdf_resp = requests.get(pdf_url, timeout=30, allow_redirects=True)
                    if pdf_resp.status_code == 200 and 'application/pdf' in pdf_resp.headers.get('content-type', ''):
                        safe_doi = doi.replace('/', '_').replace('.', '_')
                        filename = f"doi_{safe_doi}.pdf"
                        (papers_dir / filename).write_bytes(pdf_resp.content)
                        result["filename"] = filename
                        result["success"] = True
                        steps.append(f"Downloaded PDF: {filename}")
                    else:
                        raise Exception("Not a valid PDF response")
                except Exception:
                    steps.append("PDF download failed, saving metadata only")
                    result["metadata_only"] = True
                    result["filename"] = _save_metadata_only_paper(doi, metadata)
                    result["success"] = True
            else:
                steps.append("No open access PDF found, saving metadata only")
                result["metadata_only"] = True
                result["filename"] = _save_metadata_only_paper(doi, metadata)
                result["success"] = True

        # --- DOI link or bare DOI ---
        elif 'doi.org' in url or url.startswith('10.'):
            doi = url if url.startswith('10.') else url.split('doi.org/')[-1]
            steps.append(f"Detected DOI: {doi}")

            metadata = _query_crossref(doi)
            if not metadata:
                result["error"] = "CrossRef metadata lookup failed"
                return result
            result["title"] = metadata.get("title", "Unknown")
            steps.append(f"Found: {result['title']}")

            pdf_url = _find_open_access_pdf(doi)
            if pdf_url:
                steps.append("Found open access PDF")
                try:
                    pdf_resp = requests.get(pdf_url, timeout=30, allow_redirects=True)
                    if pdf_resp.status_code == 200 and 'application/pdf' in pdf_resp.headers.get('content-type', ''):
                        safe_doi = doi.replace('/', '_').replace('.', '_')
                        filename = f"doi_{safe_doi}.pdf"
                        (papers_dir / filename).write_bytes(pdf_resp.content)
                        result["filename"] = filename
                        result["success"] = True
                        steps.append(f"Downloaded PDF: {filename}")
                    else:
                        raise Exception("Not a valid PDF response")
                except Exception:
                    steps.append("PDF download failed, saving metadata only")
                    result["metadata_only"] = True
                    result["filename"] = _save_metadata_only_paper(doi, metadata)
                    result["success"] = True
            else:
                steps.append("No open access PDF, saving metadata only")
                result["metadata_only"] = True
                result["filename"] = _save_metadata_only_paper(doi, metadata)
                result["success"] = True

        # --- Direct PDF link ---
        elif url.endswith('.pdf') or 'pdf' in url.lower():
            steps.append("Detected direct PDF link")
            resp = requests.get(url, timeout=30, allow_redirects=True)
            if resp.status_code == 200:
                filename = url.split('/')[-1].split('?')[0]
                if not filename.endswith('.pdf'):
                    filename = f"downloaded_{int(time.time())}.pdf"
                (papers_dir / filename).write_bytes(resp.content)
                result["filename"] = filename
                result["success"] = True
                steps.append(f"Downloaded: {filename}")
            else:
                result["error"] = f"Download failed (HTTP {resp.status_code})"
                return result
        else:
            result["error"] = "Unrecognized URL format. Supported: arXiv, DOI, publisher pages, direct PDF links."
            return result

        # Run ingestion pipeline if we have a PDF (not metadata-only)
        if result["filename"] and not result["metadata_only"]:
            steps.append("Running ingestion pipeline...")
            try:
                _run_ingestion_pipeline()
                steps.append("Pipeline complete")
            except RuntimeError as e:
                result["error"] = str(e)
                return result

    except requests.exceptions.Timeout:
        result["error"] = "Request timed out"
    except requests.exceptions.ConnectionError:
        result["error"] = "Connection error — check internet"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"

    return result


@router.post("/upload")
async def upload_pdfs(files: list[UploadFile] = File(...)):
    """
    Upload one or more PDF files and process through the ingestion pipeline.
    Re-implements process_uploaded_pdfs without Streamlit dependencies.
    """
    papers_dir = Path("papers")
    papers_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    skipped = []
    failed = []

    for uploaded in files:
        filename = uploaded.filename or f"upload_{int(time.time())}.pdf"
        target = papers_dir / filename

        if target.exists():
            skipped.append(filename)
            continue

        try:
            content = await uploaded.read()
            target.write_bytes(content)
            saved.append(filename)
        except Exception as e:
            failed.append({"filename": filename, "error": str(e)})

    # Run pipeline if any files were saved
    pipeline_error = None
    if saved:
        try:
            _run_ingestion_pipeline()
        except RuntimeError as e:
            pipeline_error = str(e)

    return {
        "saved": saved,
        "skipped": skipped,
        "failed": failed,
        "pipeline_error": pipeline_error,
        "total_processed": len(saved),
    }


@router.post("/doi")
def import_by_doi(body: DOIImportRequest):
    """Import a paper by DOI (convenience wrapper around /url)."""
    return import_from_url(URLImportRequest(url=f"https://doi.org/{body.doi}"))


@router.post("/metadata-only")
def import_metadata_only(body: MetadataOnlyImportRequest):
    """Import a metadata-only paper (no PDF) by DOI."""
    metadata = _query_crossref(body.doi)
    if not metadata:
        raise HTTPException(status_code=404, detail="Could not find metadata for this DOI")

    filename = _save_metadata_only_paper(body.doi, metadata)
    return {
        "success": True,
        "filename": filename,
        "title": metadata.get("title", "Unknown"),
        "metadata_only": True,
    }


@router.post("/enrich")
def enrich_papers(body: EnrichRequest):
    """
    Enrich papers with metadata from CrossRef/Semantic Scholar.
    If filenames provided, enrich those specific papers.
    Otherwise, enrich all papers missing metadata.
    """
    from lib.app_helpers import enrich_library_metadata

    steps = []

    def progress_cb(msg):
        steps.append(msg)

    result = enrich_library_metadata(
        max_papers=body.max_papers,
        progress_callback=progress_cb,
    )

    return {**result, "steps": steps}


@router.post("/bulk-doi")
def import_bulk_dois(body: BulkDOIRequest):
    """Import multiple papers by DOI in one request."""
    results = []
    for doi in body.dois:
        doi = doi.strip()
        if not doi:
            continue
        try:
            res = import_from_url(URLImportRequest(url=f"https://doi.org/{doi}"))
            results.append({"doi": doi, **res})
        except Exception as e:
            results.append({"doi": doi, "success": False, "error": str(e)})
    succeeded = sum(1 for r in results if r.get("success"))
    return {"results": results, "total": len(results), "succeeded": succeeded}


@router.get("/logs")
def get_import_logs():
    """Return the list of import log files."""
    logs_dir = Path("data/import_logs")
    if not logs_dir.exists():
        return {"logs": []}
    logs = []
    for f in sorted(logs_dir.iterdir(), reverse=True):
        if f.is_file() and f.suffix == ".json":
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                logs.append({
                    "filename": f.name,
                    "timestamp": data.get("timestamp", ""),
                    "source": data.get("source", ""),
                    "papers_added": data.get("papers_added", 0),
                    "papers_skipped": data.get("papers_skipped", 0),
                    "errors": data.get("errors", 0),
                })
            except Exception:
                logs.append({"filename": f.name, "error": "Could not parse log"})
    return {"logs": logs, "total": len(logs)}
