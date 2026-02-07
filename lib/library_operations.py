"""
Library operations - functions for managing papers in the library.
Extracted from app_monolith.py for use in independent pages.
"""
import json
import re
import time
import sys
import requests
import subprocess
import shutil
import streamlit as st
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import urllib.parse

# Import from lib modules
from lib import rag
from lib.app_helpers import query_crossref_for_metadata


def save_metadata_only_paper(doi: str, crossref_metadata: dict) -> str:
    """Save metadata-only paper to ChromaDB and metadata.json"""
    import chromadb

    safe_doi = doi.replace('/', '_').replace('.', '_')
    filename = f"doi_{safe_doi}.pdf"

    # Save to metadata.json
    metadata_file = Path("data/metadata.json")
    metadata_file.parent.mkdir(parents=True, exist_ok=True)

    all_metadata = {}
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            all_metadata = json.load(f)

    all_metadata[filename] = {
        'filename': filename,
        'title': crossref_metadata.get('title', 'Unknown Title'),
        'authors': crossref_metadata.get('authors', []),
        'year': crossref_metadata.get('year', ''),
        'journal': crossref_metadata.get('journal', ''),
        'doi': doi,
        'chemistries': [],
        'topics': [],
        'application': 'general',
        'paper_type': 'experimental',
        'metadata_only': True,
        'date_added': datetime.now().isoformat(),
        'abstract': crossref_metadata.get('abstract', ''),
        'author_keywords': crossref_metadata.get('author_keywords', []),
        'volume': crossref_metadata.get('volume', ''),
        'issue': crossref_metadata.get('issue', ''),
        'pages': crossref_metadata.get('pages', ''),
        'source_url': '',
        'notes': '',
        'references': crossref_metadata.get('references', [])
    }

    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, indent=2, ensure_ascii=False)

    # Add to ChromaDB using the DatabaseClient to ensure consistency
    from lib.rag import DatabaseClient

    # First clear any cached collection to force a fresh connection
    DatabaseClient.clear_cache()

    # Now get a fresh collection reference
    collection = DatabaseClient.get_collection()

    doc_id = f"{filename}_metadata_only"
    try:
        collection.delete(ids=[doc_id])
    except:
        pass

    collection.add(
        documents=[f"Metadata-only: {crossref_metadata.get('title', '')}. DOI: {doi}"],
        metadatas=[{
            'filename': filename,
            'page_num': 0,
            'section_name': 'metadata_only',
            'title': crossref_metadata.get('title', ''),
            'authors': ';'.join(crossref_metadata.get('authors', [])) if crossref_metadata.get('authors') else '',
            'year': crossref_metadata.get('year', ''),
            'journal': crossref_metadata.get('journal', ''),
            'doi': doi,
            'chemistries': '',
            'topics': '',
            'application': 'general',
            'paper_type': 'experimental',
            'abstract': crossref_metadata.get('abstract', ''),
            'author_keywords': ';'.join(crossref_metadata.get('author_keywords', [])),
            'volume': crossref_metadata.get('volume', ''),
            'issue': crossref_metadata.get('issue', ''),
            'pages': crossref_metadata.get('pages', ''),
            'date_added': datetime.now().isoformat(),
            'source_url': ''
        }],
        ids=[doc_id]
    )

    # Clear cache again so next get_paper_library() call sees the new paper
    DatabaseClient.clear_cache()

    return filename


def process_url_import(url: str, progress_container) -> Dict[str, Any]:
    """
    Import a paper from URL (arXiv, DOI, or direct PDF link).

    Args:
        url: URL to import from
        progress_container: Streamlit container for progress updates

    Returns:
        Dictionary with import results
    """
    papers_dir = Path("papers")
    papers_dir.mkdir(parents=True, exist_ok=True)

    result = {
        'success': False,
        'title': None,
        'filename': None,
        'error': None,
        'metadata_only': False
    }

    url = url.strip()

    with progress_container:
        st.info(f"🔗 Processing URL: {url}")

        try:
            # Detect URL type
            if 'arxiv.org' in url:
                # arXiv link
                st.caption("📄 Detected: arXiv paper")

                # Extract arXiv ID
                arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', url)
                if not arxiv_match:
                    result['error'] = "Invalid arXiv URL format"
                    return result

                arxiv_id = arxiv_match.group(1)
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                filename = f"arxiv_{arxiv_id.replace('.', '_')}.pdf"

                st.caption(f"📥 Downloading from arXiv (ID: {arxiv_id})...")

                # Download PDF
                response = requests.get(pdf_url, timeout=30)
                if response.status_code == 200:
                    filepath = papers_dir / filename
                    with open(filepath, 'wb') as f:
                        f.write(response.content)

                    result['filename'] = filename
                    result['success'] = True
                    st.caption(f"✓ Downloaded: {filename}")
                else:
                    result['error'] = f"Failed to download from arXiv (HTTP {response.status_code})"
                    return result

            elif any(publisher in url.lower() for publisher in [
                'sciencedirect.com', 'ieeexplore.ieee.org', 'onlinelibrary.wiley.com',
                'link.springer.com', 'nature.com/articles', 'mdpi.com', 'cell.com',
                'thelancet.com', 'pubs.acs.org', 'pubs.rsc.org', 'iopscience.iop.org'
            ]):
                # Publisher article page
                st.caption("📰 Detected: Publisher article page")
                st.caption(f"🔍 Extracting DOI from page...")

                doi = None

                # Try to extract DOI from URL pattern first
                if 'doi.org' in url or '/doi/' in url:
                    # DOI is in the URL
                    doi_match = re.search(r'(?:doi\.org/|/doi/(?:abs/|full/)?)(10\.\d+/[^\s?&#]+)', url)
                    if doi_match:
                        doi = doi_match.group(1)

                # If not in URL, scrape from page
                if not doi:
                    try:
                        st.caption("🌐 Fetching page to extract DOI...")
                        # Use more complete browser headers to avoid blocking
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'DNT': '1',
                            'Connection': 'keep-alive',
                            'Upgrade-Insecure-Requests': '1',
                            'Sec-Fetch-Dest': 'document',
                            'Sec-Fetch-Mode': 'navigate',
                            'Sec-Fetch-Site': 'none',
                            'Cache-Control': 'max-age=0'
                        }

                        page_response = requests.get(url, timeout=15, headers=headers)

                        if page_response.status_code == 403:
                            st.warning("⚠️ Publisher blocked automated access (403 Forbidden)")
                            st.info("💡 Workaround: Manually enter the DOI instead, or download the PDF and upload it.")
                            result['error'] = "Publisher blocked automated access. Try entering DOI directly or upload PDF."
                            return result
                        elif page_response.status_code != 200:
                            st.warning(f"⚠️ Could not fetch page (HTTP {page_response.status_code})")
                            result['error'] = f"HTTP {page_response.status_code} when fetching page"
                            return result

                        if page_response.status_code == 200:
                            from bs4 import BeautifulSoup
                            soup = BeautifulSoup(page_response.text, 'html.parser')

                            # Try all common meta tag patterns
                            meta_tags_to_try = [
                                ('name', 'citation_doi'),
                                ('name', 'DC.Identifier'),
                                ('property', 'citation_doi'),
                                ('name', 'DOI'),
                                ('name', 'dc.identifier'),
                                ('property', 'og:identifier'),
                                ('name', 'prism.doi'),  # Common in ScienceDirect
                            ]

                            for attr, value in meta_tags_to_try:
                                doi_meta = soup.find('meta', {attr: value})
                                if doi_meta and doi_meta.get('content'):
                                    doi_content = doi_meta['content'].strip()
                                    # Extract just the DOI part
                                    if 'doi.org/' in doi_content:
                                        doi = doi_content.split('doi.org/')[-1]
                                    elif doi_content.startswith('10.'):
                                        doi = doi_content

                                    if doi:
                                        st.caption(f"✓ Found DOI in meta tag: {attr}={value}")
                                        break

                            # If still no DOI, search page HTML for DOI pattern
                            if not doi:
                                # Look for DOI in script tags (ScienceDirect often has it in JSON-LD)
                                script_tags = soup.find_all('script', {'type': 'application/ld+json'})
                                for script in script_tags:
                                    doi_match = re.search(r'"doi"\s*:\s*"(10\.\d+/[^"]+)"', script.string or '')
                                    if doi_match:
                                        doi = doi_match.group(1)
                                        st.caption("✓ Found DOI in JSON-LD schema")
                                        break

                            # Last resort: search entire page text for DOI pattern
                            if not doi:
                                doi_pattern = re.search(r'\b(10\.\d{4,}/[^\s<>"\']+)\b', page_response.text)
                                if doi_pattern:
                                    candidate = doi_pattern.group(1)
                                    # Clean up common trailing characters
                                    candidate = re.sub(r'[,;.\)]+$', '', candidate)
                                    if candidate:
                                        doi = candidate
                                        st.caption("✓ Found DOI in page content")

                    except Exception as e:
                        st.warning(f"⚠️ Could not fetch page: {str(e)}")

                if not doi:
                    result['error'] = "Could not extract DOI from publisher page"
                    return result

                st.caption(f"✓ Found DOI: {doi}")

                # Now proceed with DOI-based lookup
                st.caption(f"📖 Looking up metadata for DOI: {doi}")

                # Get metadata from CrossRef
                metadata = query_crossref_for_metadata(doi)
                if not metadata:
                    result['error'] = "Could not retrieve metadata from CrossRef"
                    return result

                result['title'] = metadata.get('title', 'Unknown')
                st.caption(f"✓ Found: {result['title']}")

                # Try to find open access PDF via Unpaywall
                st.caption("🔓 Checking for open access PDF via Unpaywall...")

                unpaywall_url = f"https://api.unpaywall.org/v2/{doi}?email=researcher@example.com"
                unpaywall_response = requests.get(unpaywall_url, timeout=10)

                pdf_url = None
                if unpaywall_response.status_code == 200:
                    unpaywall_data = unpaywall_response.json()
                    if unpaywall_data.get('is_oa') and unpaywall_data.get('best_oa_location'):
                        pdf_url = unpaywall_data['best_oa_location'].get('url_for_pdf')

                if pdf_url:
                    st.caption(f"✓ Found open access PDF!")
                    st.caption(f"📥 Downloading from {urllib.parse.urlparse(pdf_url).netloc}...")

                    # Download PDF
                    try:
                        pdf_response = requests.get(pdf_url, timeout=30, allow_redirects=True)
                        if pdf_response.status_code == 200 and pdf_response.headers.get('content-type', '').startswith('application/pdf'):
                            # Create safe filename from DOI
                            safe_doi = doi.replace('/', '_').replace('.', '_')
                            filename = f"doi_{safe_doi}.pdf"
                            filepath = papers_dir / filename

                            with open(filepath, 'wb') as f:
                                f.write(pdf_response.content)

                            result['filename'] = filename
                            result['success'] = True
                            st.caption(f"✓ Downloaded: {filename}")
                        else:
                            st.warning("⚠️ Could not download PDF (may be paywalled)")
                            result['metadata_only'] = True
                            result['filename'] = save_metadata_only_paper(doi, metadata)
                            result['success'] = True
                    except Exception as e:
                        st.warning(f"⚠️ PDF download failed: {str(e)}")
                        result['metadata_only'] = True
                        result['filename'] = save_metadata_only_paper(doi, metadata)
                        result['success'] = True
                else:
                    st.warning("⚠️ No open access PDF found - this paper may be paywalled")
                    result['metadata_only'] = True
                    result['filename'] = save_metadata_only_paper(doi, metadata)
                    result['success'] = True

            elif 'doi.org' in url or url.startswith('10.'):
                # DOI link or DOI string
                st.caption("🔍 Detected: DOI")

                # Extract DOI
                if url.startswith('10.'):
                    doi = url
                else:
                    doi = url.split('doi.org/')[-1]

                st.caption(f"📖 Looking up metadata for DOI: {doi}")

                # Get metadata from CrossRef
                metadata = query_crossref_for_metadata(doi)
                if not metadata:
                    result['error'] = "Could not retrieve metadata from CrossRef"
                    return result

                result['title'] = metadata.get('title', 'Unknown')
                st.caption(f"✓ Found: {result['title']}")

                # Try to find open access PDF via Unpaywall
                st.caption("🔓 Checking for open access PDF via Unpaywall...")

                unpaywall_url = f"https://api.unpaywall.org/v2/{doi}?email=researcher@example.com"
                unpaywall_response = requests.get(unpaywall_url, timeout=10)

                pdf_url = None
                if unpaywall_response.status_code == 200:
                    unpaywall_data = unpaywall_response.json()
                    if unpaywall_data.get('is_oa') and unpaywall_data.get('best_oa_location'):
                        pdf_url = unpaywall_data['best_oa_location'].get('url_for_pdf')

                if pdf_url:
                    st.caption(f"✓ Found open access PDF!")
                    st.caption(f"📥 Downloading from {urllib.parse.urlparse(pdf_url).netloc}...")

                    # Download PDF
                    try:
                        pdf_response = requests.get(pdf_url, timeout=30, allow_redirects=True)
                        if pdf_response.status_code == 200 and pdf_response.headers.get('content-type', '').startswith('application/pdf'):
                            # Create safe filename from DOI
                            safe_doi = doi.replace('/', '_').replace('.', '_')
                            filename = f"doi_{safe_doi}.pdf"
                            filepath = papers_dir / filename

                            with open(filepath, 'wb') as f:
                                f.write(pdf_response.content)

                            result['filename'] = filename
                            result['success'] = True
                            st.caption(f"✓ Downloaded: {filename}")
                        else:
                            st.warning("⚠️ Could not download PDF (may be paywalled)")
                            result['metadata_only'] = True
                            result['filename'] = save_metadata_only_paper(doi, metadata)
                            result['success'] = True
                    except Exception as e:
                        st.warning(f"⚠️ PDF download failed: {str(e)}")
                        result['metadata_only'] = True
                        result['filename'] = save_metadata_only_paper(doi, metadata)
                        result['success'] = True
                else:
                    st.warning("⚠️ No open access PDF found - this paper may be paywalled")
                    result['metadata_only'] = True
                    result['filename'] = save_metadata_only_paper(doi, metadata)
                    result['success'] = True

            elif url.endswith('.pdf') or 'pdf' in url.lower():
                # Direct PDF link
                st.caption("📄 Detected: Direct PDF link")
                st.caption(f"📥 Downloading PDF...")

                # Download PDF
                response = requests.get(url, timeout=30, allow_redirects=True)
                if response.status_code == 200:
                    # Try to get filename from URL or Content-Disposition header
                    filename = None
                    if 'content-disposition' in response.headers:
                        cd = response.headers['content-disposition']
                        filename_match = re.findall('filename="?([^"]+)"?', cd)
                        if filename_match:
                            filename = filename_match[0]

                    if not filename:
                        # Extract from URL
                        filename = url.split('/')[-1].split('?')[0]
                        if not filename.endswith('.pdf'):
                            filename = f"downloaded_{int(time.time())}.pdf"

                    filepath = papers_dir / filename
                    with open(filepath, 'wb') as f:
                        f.write(response.content)

                    result['filename'] = filename
                    result['success'] = True
                    st.caption(f"✓ Downloaded: {filename}")
                else:
                    result['error'] = f"Failed to download PDF (HTTP {response.status_code})"
                    return result
            else:
                result['error'] = "Unrecognized URL format. Supported: arXiv, DOI (doi.org/...), or direct PDF links"
                return result

            # Run ingestion pipeline if we have a PDF
            if result['filename'] and not result['metadata_only']:
                st.divider()
                st.info(f"📊 Processing paper through pipeline...")

                progress_bar = st.progress(0)
                status_text = st.empty()

                try:
                    # Stage 1: Parse
                    status_text.text("Stage 1/4: Extracting text from PDF...")
                    progress_bar.progress(25)
                    subprocess.run(
                        [sys.executable, "scripts/ingest_pipeline.py", "--stage", "parse", "--new-only"],
                        check=True,
                        capture_output=True,
                        text=True
                    )

                    # Stage 2: Chunk
                    status_text.text("Stage 2/4: Creating chunks...")
                    progress_bar.progress(50)
                    subprocess.run(
                        [sys.executable, "scripts/ingest_pipeline.py", "--stage", "chunk", "--new-only"],
                        check=True,
                        capture_output=True,
                        text=True
                    )

                    # Stage 3: Metadata
                    status_text.text("Stage 3/4: Extracting metadata...")
                    progress_bar.progress(75)
                    subprocess.run(
                        [sys.executable, "scripts/ingest_pipeline.py", "--stage", "metadata", "--new-only"],
                        check=True,
                        capture_output=True,
                        text=True
                    )

                    # Stage 4: Embed
                    status_text.text("Stage 4/4: Creating embeddings...")
                    progress_bar.progress(90)
                    subprocess.run(
                        [sys.executable, "scripts/ingest_pipeline.py", "--stage", "embed"],
                        check=True,
                        capture_output=True,
                        text=True
                    )

                    progress_bar.progress(100)
                    status_text.text("✅ Processing complete!")

                except subprocess.CalledProcessError as e:
                    result['error'] = f"Pipeline processing failed: {str(e)}"
                    return result

        except requests.exceptions.Timeout:
            result['error'] = "Request timed out - server not responding"
        except requests.exceptions.ConnectionError:
            result['error'] = "Connection error - check your internet connection"
        except Exception as e:
            result['error'] = f"Unexpected error: {str(e)}"

    return result


def process_uploaded_pdfs(uploaded_files: list, progress_container, replace_duplicates: bool = False) -> Dict[str, Any]:
    """
    Process uploaded PDF files through the ingestion pipeline.

    Args:
        uploaded_files: List of uploaded file objects from st.file_uploader
        progress_container: Streamlit container for progress updates
        replace_duplicates: If True, replace existing files; if False, skip them

    Returns:
        Dictionary with processing results
    """
    papers_dir = Path("papers")
    papers_dir.mkdir(parents=True, exist_ok=True)

    results = {
        'saved': [],
        'replaced': [],
        'skipped': [],
        'failed': [],
        'total': len(uploaded_files)
    }

    with progress_container:
        # Show immediate feedback
        st.info(f"🚀 Starting to process {len(uploaded_files)} file(s)...")
        time.sleep(0.5)  # Brief pause so user sees the message

    # Save uploaded files
    for i, uploaded_file in enumerate(uploaded_files, 1):
        filename = uploaded_file.name
        target_path = papers_dir / filename
        is_replacement = False

        with progress_container:
            st.caption(f"📄 Saving file {i}/{len(uploaded_files)}: {filename}")

        # Check for duplicates
        if target_path.exists():
            if replace_duplicates:
                # Delete the old file and mark for replacement
                try:
                    target_path.unlink()
                    is_replacement = True
                    with progress_container:
                        st.caption(f"♻️ Replacing existing file: {filename}")
                except Exception as e:
                    results['failed'].append((filename, f"Failed to replace: {str(e)}"))
                    with progress_container:
                        st.error(f"❌ Failed to replace {filename}: {str(e)}")
                    continue
            else:
                results['skipped'].append(filename)
                with progress_container:
                    st.caption(f"⏭️ Skipping duplicate: {filename}")
                continue

        try:
            # Save the file
            with open(target_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())

            if is_replacement:
                results['replaced'].append(filename)
            else:
                results['saved'].append(filename)

            with progress_container:
                st.caption(f"✓ Saved: {filename}")

        except Exception as e:
            results['failed'].append((filename, str(e)))
            with progress_container:
                st.error(f"❌ Failed to save {filename}: {str(e)}")

    # Run ingestion pipeline if we saved or replaced any files
    total_to_process = len(results['saved']) + len(results['replaced'])
    if total_to_process > 0:
        all_papers = results['saved'] + results['replaced']

        with progress_container:
            st.divider()
            if results['replaced']:
                st.info(f"📊 Processing {total_to_process} paper(s) through pipeline ({len(results['replaced'])} replacement(s))...")
            else:
                st.info(f"📊 Processing {total_to_process} new paper(s) through pipeline...")

            overall_progress = st.progress(0)
            stage_status = st.empty()
            paper_status = st.empty()

            try:
                # Stage 1: Parse (Extract text)
                stage_status.markdown("**Stage 1/4: 📄 Extracting text from PDFs**")
                for i, paper in enumerate(all_papers, 1):
                    paper_status.text(f"   Processing paper {i}/{total_to_process}: {paper}")
                    overall_progress.progress(int((i / total_to_process) * 20))
                    time.sleep(0.1)  # Brief pause for visibility

                result = subprocess.run(
                    [sys.executable, "scripts/ingest_pipeline.py", "--stage", "parse", "--new-only"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

                overall_progress.progress(25)
                paper_status.text("   ✓ Text extraction complete")
                time.sleep(0.3)

                # Stage 2: Chunk
                stage_status.markdown("**Stage 2/4: 📑 Creating chunks**")
                for i, paper in enumerate(all_papers, 1):
                    paper_status.text(f"   Chunking paper {i}/{total_to_process}: {paper}")
                    overall_progress.progress(25 + int((i / total_to_process) * 20))
                    time.sleep(0.1)

                result = subprocess.run(
                    [sys.executable, "scripts/ingest_pipeline.py", "--stage", "chunk", "--new-only"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

                overall_progress.progress(50)
                paper_status.text("   ✓ Chunking complete")
                time.sleep(0.3)

                # Stage 3: Metadata
                stage_status.markdown("**Stage 3/4: 🔍 Extracting metadata**")
                paper_status.text("   Using Claude to analyze papers and extract metadata...")
                overall_progress.progress(55)

                for i, paper in enumerate(all_papers, 1):
                    paper_status.text(f"   Analyzing paper {i}/{total_to_process}: {paper}")
                    # This stage takes longer, so update less frequently
                    overall_progress.progress(55 + int((i / total_to_process) * 20))
                    time.sleep(0.2)

                result = subprocess.run(
                    [sys.executable, "scripts/ingest_pipeline.py", "--stage", "metadata", "--new-only"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

                overall_progress.progress(75)
                paper_status.text("   ✓ Metadata extraction complete")
                time.sleep(0.3)

                # Stage 4: Embed
                stage_status.markdown("**Stage 4/4: 🧮 Generating embeddings and indexing**")
                paper_status.text("   Creating vector embeddings for semantic search...")
                overall_progress.progress(80)

                for i, paper in enumerate(all_papers, 1):
                    paper_status.text(f"   Embedding paper {i}/{total_to_process}: {paper}")
                    overall_progress.progress(80 + int((i / total_to_process) * 15))
                    time.sleep(0.1)

                result = subprocess.run(
                    [sys.executable, "scripts/ingest_pipeline.py", "--stage", "embed"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

                overall_progress.progress(100)
                paper_status.text("   ✓ Embeddings generated and indexed")
                stage_status.markdown("**✅ All stages complete!**")
                time.sleep(0.5)

            except subprocess.CalledProcessError as e:
                stage_status.markdown("**❌ Pipeline Error**")
                paper_status.text("")
                error_msg = e.stderr if e.stderr else str(e)
                st.error(f"Pipeline failed: {error_msg}")

                # Show detailed error if available
                if e.stdout:
                    with st.expander("Show pipeline output"):
                        st.code(e.stdout)

                # Mark all as failed
                all_files = results['saved'] + results['replaced']
                for filename in all_files:
                    results['failed'].append((filename, "Pipeline processing failed"))
                results['saved'] = []
                results['replaced'] = []

    return results


def soft_delete_paper(filename: str) -> Dict[str, Any]:
    """
    Soft delete a paper by marking it as deleted and moving PDF to trash.

    Args:
        filename: Paper filename

    Returns:
        Dict with success status and message
    """
    try:
        # Load metadata
        metadata_file = Path("data/metadata.json")
        if not metadata_file.exists():
            return {'success': False, 'message': 'Metadata file not found'}

        with open(metadata_file, 'r', encoding='utf-8') as f:
            all_metadata = json.load(f)

        if filename not in all_metadata:
            return {'success': False, 'message': 'Paper not found in metadata'}

        # Mark as deleted in metadata
        all_metadata[filename]['deleted_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Save updated metadata
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, indent=2, ensure_ascii=False)

        # Move PDF to trash folder if it exists
        pdf_path = Path("papers") / filename
        if pdf_path.exists():
            trash_dir = Path("papers/trash")
            trash_dir.mkdir(parents=True, exist_ok=True)

            trash_path = trash_dir / filename
            shutil.move(str(pdf_path), str(trash_path))

        # Remove from ChromaDB
        try:
            db = rag.DatabaseClient()
            db.collection.delete(where={"filename": filename})
        except Exception as e:
            # Non-fatal if ChromaDB deletion fails
            pass

        return {
            'success': True,
            'message': f'Moved "{all_metadata[filename].get("title", filename)}" to trash'
        }

    except Exception as e:
        return {'success': False, 'message': f'Error: {str(e)}'}
