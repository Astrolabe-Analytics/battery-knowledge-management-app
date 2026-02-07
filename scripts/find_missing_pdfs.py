#!/usr/bin/env python3
"""
Find and download open access PDFs for metadata-only papers.

Sources (in priority order):
1. ArXiv - Free, instant, no rate limit
2. PubMed Central (PMC) - Free, instant
3. Semantic Scholar - Good academic coverage
4. Unpaywall - Best for journal articles

Usage:
    python scripts/find_missing_pdfs.py                 # Search all papers
    python scripts/find_missing_pdfs.py --limit 100     # Test with 100 papers
    python scripts/find_missing_pdfs.py --doi-first     # Prioritize papers with DOIs
    python scripts/find_missing_pdfs.py --dry-run       # Preview without downloading
    python scripts/find_missing_pdfs.py --resume        # Resume from checkpoint
    python scripts/find_missing_pdfs.py --sync          # Sync metadata.json to ChromaDB
"""

import json
import time
import requests
import argparse
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from tqdm import tqdm


# Paths
BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"
PAPERS_DIR = BASE_DIR / "papers"
CHECKPOINT_FILE = BASE_DIR / "data" / "pdf_search_checkpoint.json"
LOG_FILE = BASE_DIR / "data" / "pdf_search_log.txt"


def load_metadata() -> dict:
    """Load metadata.json"""
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_metadata(metadata: dict):
    """Save metadata.json"""
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def load_checkpoint() -> dict:
    """Load checkpoint file"""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'processed': [], 'found': 0, 'failed': 0}


def save_checkpoint(checkpoint: dict):
    """Save checkpoint file"""
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(checkpoint, f, indent=2)


def log_message(message: str):
    """Append message to log file"""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {message}\n")


def validate_pdf(file_path: Path) -> bool:
    """
    Verify downloaded file is actually a PDF.
    Some URLs return HTML login pages or error pages.
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(5)
            if header != b'%PDF-':
                os.remove(file_path)
                return False
        return True
    except Exception:
        return False


def sanitize_filename(title: str, max_length: int = 200) -> str:
    """Create safe filename from paper title"""
    import re
    # Remove special characters
    safe_title = re.sub(r'[^\w\s-]', '', title)
    # Replace spaces with underscores
    safe_title = re.sub(r'[-\s]+', '_', safe_title)
    # Truncate to max length
    if len(safe_title) > max_length:
        safe_title = safe_title[:max_length]
    return safe_title + '.pdf'


def get_arxiv_pdf(arxiv_id: str) -> Optional[Tuple[str, bytes]]:
    """
    Download PDF from ArXiv.
    ArXiv IDs: YYMM.NNNNN or YYMM.NNNNNN (e.g., 2301.12345)
    URL: https://arxiv.org/pdf/{arxiv_id}.pdf
    """
    try:
        # Clean arXiv ID (remove version if present)
        arxiv_id = arxiv_id.split('v')[0]

        url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (BatteryResearchLibrary/1.0)'
        })

        if response.status_code == 200:
            return ('arxiv', response.content)
        return None
    except Exception as e:
        log_message(f"ArXiv download failed for {arxiv_id}: {e}")
        return None


def get_pmc_pdf(pmc_id: str) -> Optional[Tuple[str, bytes]]:
    """
    Download PDF from PubMed Central.
    PMC IDs: PMC1234567 or just the number
    URL: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{id}/pdf/
    """
    try:
        # Clean PMC ID
        pmc_id = pmc_id.replace('PMC', '')

        url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (BatteryResearchLibrary/1.0)'
        })

        if response.status_code == 200 and response.headers.get('content-type', '').startswith('application/pdf'):
            return ('pmc', response.content)
        return None
    except Exception as e:
        log_message(f"PMC download failed for PMC{pmc_id}: {e}")
        return None


def search_semantic_scholar(doi: str = None, title: str = None) -> Optional[Tuple[str, str]]:
    """
    Search Semantic Scholar for open access PDF.
    Returns (source, pdf_url) if found.

    Rate limit: 100 requests per 5 minutes
    """
    try:
        api_key = os.environ.get('SEMANTIC_SCHOLAR_API_KEY')
        headers = {'User-Agent': 'BatteryResearchLibrary/1.0'}
        if api_key:
            headers['x-api-key'] = api_key

        # Search by DOI first (more accurate)
        if doi:
            url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
            params = {'fields': 'isOpenAccess,openAccessPdf,externalIds'}

            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()

                # Check for ArXiv ID
                external_ids = data.get('externalIds', {})
                if external_ids.get('ArXiv'):
                    return ('semantic_scholar_arxiv', external_ids['ArXiv'])

                # Check for PMC ID
                if external_ids.get('PubMedCentral'):
                    return ('semantic_scholar_pmc', external_ids['PubMedCentral'])

                # Check for open access PDF
                if data.get('isOpenAccess') and data.get('openAccessPdf'):
                    pdf_url = data['openAccessPdf'].get('url')
                    if pdf_url:
                        return ('semantic_scholar', pdf_url)

        # Fallback to title search
        if title:
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                'query': title,
                'limit': 1,
                'fields': 'title,isOpenAccess,openAccessPdf,externalIds'
            }

            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    paper = data['data'][0]

                    # Check title similarity (>90%)
                    import re
                    def normalize(s):
                        return re.sub(r'[^\w\s]', '', s.lower()).strip()

                    if normalize(paper.get('title', '')) == normalize(title):
                        # Check for ArXiv ID
                        external_ids = paper.get('externalIds', {})
                        if external_ids.get('ArXiv'):
                            return ('semantic_scholar_arxiv', external_ids['ArXiv'])

                        # Check for PMC ID
                        if external_ids.get('PubMedCentral'):
                            return ('semantic_scholar_pmc', external_ids['PubMedCentral'])

                        # Check for open access PDF
                        if paper.get('isOpenAccess') and paper.get('openAccessPdf'):
                            pdf_url = paper['openAccessPdf'].get('url')
                            if pdf_url:
                                return ('semantic_scholar', pdf_url)

        return None

    except Exception as e:
        log_message(f"Semantic Scholar search failed: {e}")
        return None


def search_unpaywall(doi: str) -> Optional[Tuple[str, str]]:
    """
    Search Unpaywall for open access PDF.
    Returns (source, pdf_url) if found.

    Requires DOI. Rate limit: Be polite (1 req/sec)
    """
    try:
        email = os.environ.get('UNPAYWALL_EMAIL', 'user@example.com')
        url = f"https://api.unpaywall.org/v2/{doi}"
        params = {'email': email}

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('is_oa') and data.get('best_oa_location'):
                pdf_url = data['best_oa_location'].get('url_for_pdf')
                if pdf_url:
                    return ('unpaywall', pdf_url)

        return None

    except Exception as e:
        log_message(f"Unpaywall search failed for {doi}: {e}")
        return None


def download_pdf(url: str) -> Optional[bytes]:
    """Download PDF from URL"""
    try:
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (BatteryResearchLibrary/1.0)'
        })

        if response.status_code == 200:
            return response.content
        return None

    except Exception as e:
        log_message(f"Download failed for {url}: {e}")
        return None


def find_and_download_pdf(paper: dict, filename: str, dry_run: bool = False) -> Optional[str]:
    """
    Try all sources to find and download PDF for a paper.
    Returns source name if successful, None otherwise.

    Source priority:
    1. ArXiv (if ID available)
    2. PMC (if ID available)
    3. Semantic Scholar
    4. Unpaywall
    """
    title = paper.get('title', '')
    doi = paper.get('doi', '')

    # Try ArXiv first (fastest, no rate limit)
    arxiv_id = paper.get('arxiv_id')
    if arxiv_id:
        result = get_arxiv_pdf(arxiv_id)
        if result:
            source, pdf_content = result
            if not dry_run:
                pdf_path = PAPERS_DIR / filename
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_content)
                if validate_pdf(pdf_path):
                    return source
            else:
                return source

    # Try PMC (free, instant)
    pmc_id = paper.get('pmc_id')
    if pmc_id:
        result = get_pmc_pdf(pmc_id)
        if result:
            source, pdf_content = result
            if not dry_run:
                pdf_path = PAPERS_DIR / filename
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_content)
                if validate_pdf(pdf_path):
                    return source
            else:
                return source

    # Try Semantic Scholar (good coverage, rate limited)
    time.sleep(1.0)  # Rate limiting
    result = search_semantic_scholar(doi=doi, title=title if not doi else None)
    if result:
        source, identifier = result

        # If it returned ArXiv or PMC ID, try those
        if 'arxiv' in source:
            arxiv_result = get_arxiv_pdf(identifier)
            if arxiv_result:
                _, pdf_content = arxiv_result
                if not dry_run:
                    pdf_path = PAPERS_DIR / filename
                    with open(pdf_path, 'wb') as f:
                        f.write(pdf_content)
                    if validate_pdf(pdf_path):
                        return source
                else:
                    return source

        elif 'pmc' in source:
            pmc_result = get_pmc_pdf(identifier)
            if pmc_result:
                _, pdf_content = pmc_result
                if not dry_run:
                    pdf_path = PAPERS_DIR / filename
                    with open(pdf_path, 'wb') as f:
                        f.write(pdf_content)
                    if validate_pdf(pdf_path):
                        return source
                else:
                    return source

        else:
            # Direct PDF URL from Semantic Scholar
            pdf_content = download_pdf(identifier)
            if pdf_content:
                if not dry_run:
                    pdf_path = PAPERS_DIR / filename
                    with open(pdf_path, 'wb') as f:
                        f.write(pdf_content)
                    if validate_pdf(pdf_path):
                        return source
                else:
                    return source

    # Try Unpaywall (best for journal articles, DOI required)
    if doi:
        time.sleep(1.0)  # Rate limiting
        result = search_unpaywall(doi)
        if result:
            source, pdf_url = result
            pdf_content = download_pdf(pdf_url)
            if pdf_content:
                if not dry_run:
                    pdf_path = PAPERS_DIR / filename
                    with open(pdf_path, 'wb') as f:
                        f.write(pdf_content)
                    if validate_pdf(pdf_path):
                        return source
                else:
                    return source

    return None


def sync_to_chromadb(metadata: dict):
    """Sync metadata.json changes to ChromaDB"""
    print("\n" + "="*60)
    print("Syncing metadata to ChromaDB...")
    print("="*60)

    from lib.rag import DatabaseClient

    updated = 0
    for filename, paper in tqdm(metadata.items(), desc="Syncing"):
        try:
            # Only sync papers that were updated (have pdf_source)
            if paper.get('pdf_source'):
                DatabaseClient.update_paper_metadata(filename, paper)
                updated += 1
        except Exception as e:
            log_message(f"ChromaDB sync failed for {filename}: {e}")

    # Clear cache
    DatabaseClient.clear_cache()

    print(f"\n✓ Synced {updated} papers to ChromaDB")


def main():
    parser = argparse.ArgumentParser(description='Find and download open access PDFs')
    parser.add_argument('--limit', type=int, help='Limit number of papers to process')
    parser.add_argument('--doi-first', action='store_true', help='Prioritize papers with DOIs')
    parser.add_argument('--dry-run', action='store_true', help='Preview without downloading')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    parser.add_argument('--sync', action='store_true', help='Sync metadata to ChromaDB (run after PDF search)')

    args = parser.parse_args()

    # If --sync flag, just sync and exit
    if args.sync:
        metadata = load_metadata()
        sync_to_chromadb(metadata)
        return

    print("="*60)
    print("BULK PDF SEARCH - Finding Open Access PDFs")
    print("="*60)
    print()

    # Load metadata
    metadata = load_metadata()

    # Find papers needing PDFs
    papers_to_search = []
    for filename, paper in metadata.items():
        # Check if needs PDF
        pdf_path = PAPERS_DIR / filename
        if not pdf_path.exists() or paper.get('metadata_only') or paper.get('pdf_status') == 'needs_pdf':
            papers_to_search.append((filename, paper))

    print(f"Found {len(papers_to_search)} papers needing PDFs")

    # Sort by priority: DOI papers first if requested
    if args.doi_first:
        papers_to_search.sort(key=lambda x: (0 if x[1].get('doi') else 1, x[0]))
        print("✓ Prioritizing papers with DOIs")

    # Apply limit
    if args.limit:
        papers_to_search = papers_to_search[:args.limit]
        print(f"Limited to {args.limit} papers")

    # Load checkpoint
    checkpoint = load_checkpoint() if args.resume else {'processed': [], 'found': 0, 'failed': 0}
    processed_set = set(checkpoint.get('processed', []))

    if args.resume and processed_set:
        print(f"✓ Resuming from checkpoint ({len(processed_set)} already processed)")

    # Filter out already processed
    papers_to_search = [(f, p) for f, p in papers_to_search if f not in processed_set]

    if not papers_to_search:
        print("\n✓ All papers already processed!")
        return

    if args.dry_run:
        print("\n⚠️ DRY RUN MODE - No files will be downloaded\n")

    print(f"\nSearching for PDFs... (Source priority: ArXiv → PMC → Semantic Scholar → Unpaywall)")
    print()

    # Statistics
    found_count = checkpoint.get('found', 0)
    failed_count = checkpoint.get('failed', 0)
    source_stats = {}

    # Process papers
    for filename, paper in tqdm(papers_to_search, desc="Searching"):
        try:
            source = find_and_download_pdf(paper, filename, dry_run=args.dry_run)

            if source:
                # Success!
                found_count += 1
                source_stats[source] = source_stats.get(source, 0) + 1

                if not args.dry_run:
                    # Update metadata
                    metadata[filename]['metadata_only'] = False
                    metadata[filename]['pdf_status'] = 'available'
                    metadata[filename]['pdf_source'] = source
                    metadata[filename]['pdf_found_date'] = datetime.now().isoformat()

                log_message(f"✓ Found PDF for {paper.get('title', filename)[:60]} (source: {source})")
            else:
                failed_count += 1
                log_message(f"✗ No PDF found for {paper.get('title', filename)[:60]}")

            # Update checkpoint
            processed_set.add(filename)
            checkpoint['processed'] = list(processed_set)
            checkpoint['found'] = found_count
            checkpoint['failed'] = failed_count

            # Save checkpoint every 50 papers
            if len(processed_set) % 50 == 0:
                save_checkpoint(checkpoint)
                if not args.dry_run:
                    save_metadata(metadata)

        except Exception as e:
            log_message(f"ERROR processing {filename}: {e}")
            failed_count += 1

    # Final save
    if not args.dry_run:
        save_metadata(metadata)
    save_checkpoint(checkpoint)

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total processed: {len(processed_set)}")
    print(f"PDFs found: {found_count} ({found_count/len(papers_to_search)*100:.1f}%)")
    print(f"Not found: {failed_count}")
    print()
    print("Sources:")
    for source, count in sorted(source_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  {source}: {count}")
    print()
    print(f"Log file: {LOG_FILE}")

    if not args.dry_run:
        print(f"\n✓ Metadata updated: {METADATA_FILE}")
        print(f"\n⚠️ Run with --sync flag to update ChromaDB:")
        print(f"   python scripts/find_missing_pdfs.py --sync")

    # Clean up checkpoint if fully complete
    if not args.limit and len(processed_set) >= len(papers_to_search):
        CHECKPOINT_FILE.unlink(missing_ok=True)
        print("\n✓ Checkpoint cleared (all papers processed)")


if __name__ == '__main__':
    main()
