"""
Bulk enrich all incomplete papers via CrossRef + S2 DOI lookup.
Writes directly to PostgreSQL.

Usage:
    python scripts/enrich_pg_bulk.py [--limit N] [--delay SECONDS] [--dry-run]
"""
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.db import get_session
from lib.models import Paper
from lib.crossref import (
    query_crossref, extract_doi_from_url, extract_doi_from_filename,
    find_doi_via_semantic_scholar, scrape_doi_from_page,
    apply_crossref_enrichment, _present,
)
from lib.db_operations import upsert_paper, save_paper_references


def main():
    parser = argparse.ArgumentParser(description="Bulk enrich papers in PostgreSQL")
    parser.add_argument("--limit", type=int, default=None, help="Max papers to process")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between CrossRef calls (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB, just show what would happen")
    parser.add_argument("--doi-only", action="store_true", help="Only process papers that already have DOIs")
    parser.add_argument("--publishers-only", action="store_true", help="Only process papers from academic publisher URLs")
    args = parser.parse_args()

    # Get all papers needing enrichment
    with get_session() as session:
        papers = session.query(Paper).filter(Paper.deleted_at.is_(None)).all()
        # Detach for use outside session
        paper_data = []
        for p in papers:
            paper_data.append({
                'filename': p.filename,
                'title': p.title,
                'authors': p.authors if isinstance(p.authors, list) else [],
                'year': p.year,
                'journal': p.journal,
                'doi': p.doi,
                'source_url': p.source_url,
                'abstract': p.abstract,
                'volume': p.volume,
                'issue': p.issue,
                'pages': p.pages,
                'author_keywords': p.author_keywords,
                'crossref_verified': p.crossref_verified,
            })

    # Filter to incomplete papers
    incomplete = []
    for p in paper_data:
        missing_authors = not p['authors'] or len(p['authors']) == 0
        missing_year = not _present(p['year'])
        missing_journal = not _present(p['journal'])
        if missing_authors or missing_year or missing_journal:
            incomplete.append(p)

    if args.doi_only:
        incomplete = [p for p in incomplete if p['doi']]

    # Prioritize: papers from academic publishers first, datasets last
    PUBLISHER_DOMAINS = ['mdpi.com', 'ieee.org', 'arxiv.org', 'sciencedirect.com',
                         'springer.com', 'nature.com', 'wiley.com', 'rsc.org',
                         'acs.org', 'iop.org', 'frontiersin.org', 'elsevier.com',
                         'pnas.org', 'aps.org', 'sae.org', 'phmsociety.org']
    DATASET_DOMAINS = ['data.mendeley.com', 'zenodo.org', 'data.4tu.nl',
                       'ieee-dataport.org', 'figshare.com', 'kaggle.com']

    if args.publishers_only:
        def is_publisher_url(p):
            url = (p.get('source_url') or '').lower()
            return any(d in url for d in PUBLISHER_DOMAINS)
        incomplete = [p for p in incomplete if is_publisher_url(p)]

    def priority_key(p):
        url = (p.get('source_url') or '').lower()
        if p.get('doi'):
            return 0  # Has DOI = highest priority
        for domain in PUBLISHER_DOMAINS:
            if domain in url:
                return 1  # Academic publisher
        for domain in DATASET_DOMAINS:
            if domain in url:
                return 3  # Dataset repo = lowest priority
        if url:
            return 2  # Has URL but unknown domain
        return 2  # Title only

    incomplete.sort(key=priority_key)

    if args.limit:
        incomplete = incomplete[:args.limit]

    print(f"Papers to enrich: {len(incomplete)}")
    if not incomplete:
        print("Nothing to do.")
        return

    enriched = 0
    failed = 0
    doi_found = 0
    errors = 0

    for idx, paper in enumerate(incomplete):
        filename = paper['filename']
        title = paper.get('title', filename)
        print(f"[{idx+1}/{len(incomplete)}] {title[:70]}...", end=" ")

        try:
            doi = paper.get('doi', '')

            # Try to find DOI
            if not doi:
                url = paper.get('source_url', '')
                if url:
                    doi = extract_doi_from_url(url)
                    if doi:
                        print(f"[DOI from URL: {doi[:40]}]", end=" ")
                        doi_found += 1

            if not doi:
                doi = extract_doi_from_filename(filename)
                if doi:
                    print(f"[DOI from filename: {doi[:40]}]", end=" ")
                    doi_found += 1

            if not doi and paper.get('source_url'):
                try:
                    doi = scrape_doi_from_page(paper['source_url'])
                    if doi:
                        print(f"[DOI from scrape: {doi[:40]}]", end=" ")
                        doi_found += 1
                except Exception:
                    pass

            if not doi and _present(title):
                doi = find_doi_via_semantic_scholar(title)
                if doi:
                    print(f"[DOI from S2: {doi[:40]}]", end=" ")
                    doi_found += 1

            if not doi:
                print("-> NO DOI")
                failed += 1
                continue

            # Query CrossRef
            crossref_data = query_crossref(doi)
            if not crossref_data:
                print(f"-> CrossRef failed for {doi[:40]}")
                failed += 1
                time.sleep(args.delay)
                continue

            # Apply enrichment
            updates = apply_crossref_enrichment(paper, crossref_data)
            if not paper.get('doi'):
                updates['doi'] = doi
            updates['crossref_verified'] = True

            updated_fields = [k for k in updates if k not in ('doi', 'crossref_verified')]

            if args.dry_run:
                print(f"-> DRY RUN: would update {', '.join(updated_fields) or 'verify only'}")
            else:
                upsert_paper(filename, updates)

                # Save references
                refs = crossref_data.get('references', [])
                if refs:
                    try:
                        save_paper_references(filename, refs)
                    except Exception:
                        pass

                print(f"-> Enriched: {', '.join(updated_fields) or 'verified'} ({len(crossref_data.get('references', []))} refs)")

            enriched += 1
            time.sleep(args.delay)

        except Exception as e:
            print(f"-> ERROR: {type(e).__name__}: {e}")
            errors += 1

    print(f"\n{'='*60}")
    print(f"Done! Enriched: {enriched}, Failed: {failed}, Errors: {errors}")
    print(f"DOIs found: {doi_found}")
    print(f"Total processed: {len(incomplete)}")


if __name__ == "__main__":
    main()
