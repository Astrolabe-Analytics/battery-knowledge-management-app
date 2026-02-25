"""
Bulk CrossRef enrichment for papers with DOIs but missing metadata.

Targets 1,341 papers that have DOIs but are missing one or more of:
  abstract, authors, year, journal, title, references, volume, issue, pages

This script:
  - Calls CrossRef directly (no Streamlit dependency)
  - Strips JATS XML from abstracts
  - Normalizes journal names
  - Saves progress every 25 papers
  - Tracks failures in a log file for later retry
  - Respects CrossRef etiquette (polite User-Agent, 0.2s delay)
  - Can be resumed (skips already-enriched papers)

Usage:
    python scripts/enrich_crossref_bulk.py [--max N] [--dry-run]
"""
import json
import time
import re
import sys
import argparse
import requests
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.jats import strip_jats

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"
LOG_FILE = BASE_DIR / "data" / "enrichment_log.json"

# Journal normalization map (common variants)
JOURNAL_NORMALIZATIONS = {
    "journal of the electrochemical society": "Journal of The Electrochemical Society",
    "journal of power sources": "Journal of Power Sources",
    "electrochimica acta": "Electrochimica Acta",
    "journal of energy storage": "Journal of Energy Storage",
    "nature energy": "Nature Energy",
    "advanced energy materials": "Advanced Energy Materials",
    "energy & environmental science": "Energy & Environmental Science",
    "acs energy letters": "ACS Energy Letters",
    "batteries & supercaps": "Batteries & Supercaps",
    "joule": "Joule",
    "applied energy": "Applied Energy",
    "energy": "Energy",
    "nano energy": "Nano Energy",
    "iscience": "iScience",
    "cell reports physical science": "Cell Reports Physical Science",
}


def normalize_journal_name(name: str) -> str:
    """Normalize common journal name variants."""
    if not name:
        return name
    key = name.lower().strip()
    return JOURNAL_NORMALIZATIONS.get(key, name)


def query_crossref(doi: str) -> dict:
    """
    Query CrossRef API for metadata, returning a processed dict.
    Returns {} on failure.
    """
    try:
        url = f"https://api.crossref.org/works/{doi}"
        headers = {
            'User-Agent': 'AstrolabeResearchLibrary/2.0 (mailto:researcher@example.com)'
        }
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            data = response.json()
            message = data.get('message', {})
            result = {}

            # Title
            titles = message.get('title', [])
            if titles:
                result['title'] = titles[0]

            # Authors (format as "Last, First")
            authors = []
            for author in message.get('author', []):
                given = author.get('given', '')
                family = author.get('family', '')
                if family:
                    if given:
                        authors.append(f"{family}, {given}")
                    else:
                        authors.append(family)
            if authors:
                result['authors'] = authors[:10]

            # Year
            published = message.get('published-print') or message.get('published-online')
            if published and 'date-parts' in published:
                date_parts = published['date-parts'][0]
                if date_parts and date_parts[0]:
                    result['year'] = str(date_parts[0])

            # Journal
            container_titles = message.get('container-title', [])
            if container_titles:
                result['journal'] = normalize_journal_name(container_titles[0])

            # Abstract (strip JATS XML)
            raw_abstract = message.get('abstract', '')
            if raw_abstract:
                result['abstract'] = strip_jats(raw_abstract)

            # Author keywords
            keywords = message.get('keywords', [])
            if keywords:
                result['author_keywords'] = keywords

            # Volume, Issue, Pages
            if message.get('volume'):
                result['volume'] = message['volume']
            if message.get('issue'):
                result['issue'] = message['issue']
            if message.get('page'):
                result['pages'] = message['page']

            # References
            refs = message.get('reference', [])
            if refs:
                result['references'] = refs

            return result

        elif response.status_code == 404:
            return {'_error': 'not_found'}
        elif response.status_code == 429:
            return {'_error': 'rate_limited'}
        else:
            return {'_error': f'http_{response.status_code}'}

    except requests.exceptions.Timeout:
        return {'_error': 'timeout'}
    except Exception as e:
        return {'_error': str(e)}


def needs_enrichment(paper: dict) -> list:
    """Return list of fields that are missing/empty for this paper."""
    missing = []
    title = (paper.get('title') or '').strip()
    if not title or title.startswith('Unknown'):
        missing.append('title')
    if not paper.get('authors'):
        missing.append('authors')
    if not paper.get('year'):
        missing.append('year')
    if not (paper.get('journal') or '').strip():
        missing.append('journal')
    if not (paper.get('abstract') or '').strip():
        missing.append('abstract')
    if not paper.get('references'):
        missing.append('references')
    if not (paper.get('volume') or '').strip():
        missing.append('volume')
    if not (paper.get('issue') or '').strip():
        missing.append('issue')
    if not (paper.get('pages') or '').strip():
        missing.append('pages')
    return missing


def apply_enrichment(paper: dict, crossref_data: dict) -> list:
    """
    Apply CrossRef data to paper, only filling in MISSING fields.
    Returns list of fields that were updated.
    """
    updated = []

    title = (paper.get('title') or '').strip()
    if (not title or title.startswith('Unknown')) and crossref_data.get('title'):
        paper['title'] = crossref_data['title']
        updated.append('title')

    if not paper.get('authors') and crossref_data.get('authors'):
        paper['authors'] = crossref_data['authors']
        updated.append('authors')

    if not paper.get('year') and crossref_data.get('year'):
        paper['year'] = crossref_data['year']
        updated.append('year')

    if not (paper.get('journal') or '').strip() and crossref_data.get('journal'):
        paper['journal'] = crossref_data['journal']
        updated.append('journal')

    if not (paper.get('abstract') or '').strip() and crossref_data.get('abstract'):
        paper['abstract'] = crossref_data['abstract']
        updated.append('abstract')

    if not paper.get('references') and crossref_data.get('references'):
        paper['references'] = crossref_data['references']
        updated.append('references')

    if not (paper.get('volume') or '').strip() and crossref_data.get('volume'):
        paper['volume'] = crossref_data['volume']
        updated.append('volume')

    if not (paper.get('issue') or '').strip() and crossref_data.get('issue'):
        paper['issue'] = crossref_data['issue']
        updated.append('issue')

    if not (paper.get('pages') or '').strip() and crossref_data.get('pages'):
        paper['pages'] = crossref_data['pages']
        updated.append('pages')

    if not paper.get('author_keywords') and crossref_data.get('author_keywords'):
        paper['author_keywords'] = crossref_data['author_keywords']
        updated.append('author_keywords')

    if updated:
        paper['crossref_verified'] = True
        paper['last_enriched'] = datetime.now().isoformat()

    return updated


def main():
    parser = argparse.ArgumentParser(description='Bulk CrossRef enrichment')
    parser.add_argument('--max', type=int, default=0, help='Max papers to process (0=all)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--delay', type=float, default=0.2, help='Delay between API calls in seconds')
    args = parser.parse_args()

    print("=" * 70)
    print("BULK CROSSREF ENRICHMENT")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)

    # Load metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    print(f"Total papers: {len(metadata)}")

    # Load previous enrichment log (for resume capability)
    enrichment_log = {}
    if LOG_FILE.exists():
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            enrichment_log = json.load(f)
        print(f"Loaded enrichment log: {len(enrichment_log)} previous entries")

    # Find papers needing enrichment (have DOI, missing fields)
    candidates = []
    for filename, paper in metadata.items():
        doi = (paper.get('doi') or '').strip()
        if not doi:
            continue

        # Skip if already enriched in this run
        if filename in enrichment_log:
            continue

        missing = needs_enrichment(paper)
        if missing:
            candidates.append((filename, doi, missing))

    print(f"Papers to enrich (have DOI, missing fields): {len(candidates)}")
    if args.max > 0:
        candidates = candidates[:args.max]
        print(f"  (limited to first {args.max})")

    if not candidates:
        print("No papers need enrichment!")
        return

    # Breakdown of what's missing
    field_counts = {}
    for _, _, missing in candidates:
        for field in missing:
            field_counts[field] = field_counts.get(field, 0) + 1
    print("\nMissing field breakdown:")
    for field, count in sorted(field_counts.items(), key=lambda x: -x[1]):
        print(f"  {field}: {count}")

    if args.dry_run:
        print("\n[DRY RUN] No changes will be made.")
        return

    # Process papers
    print(f"\nStarting enrichment (delay={args.delay}s between requests)...")
    print("-" * 70)

    stats = {
        'enriched': 0,
        'no_new_data': 0,
        'not_found': 0,
        'errors': 0,
        'rate_limited': 0,
        'fields_filled': {},
    }

    start_time = time.time()
    save_counter = 0

    for idx, (filename, doi, missing) in enumerate(candidates, 1):
        progress = (idx / len(candidates)) * 100
        safe_title = (metadata[filename].get('title') or filename)[:60]
        print(f"\n[{idx}/{len(candidates)} {progress:.0f}%] {safe_title}")
        print(f"  DOI: {doi}")
        print(f"  Missing: {', '.join(missing)}")

        # Query CrossRef
        crossref_data = query_crossref(doi)

        # Handle errors
        if '_error' in crossref_data:
            error = crossref_data['_error']
            if error == 'rate_limited':
                stats['rate_limited'] += 1
                print(f"  >> RATE LIMITED - waiting 30s...")
                time.sleep(30)
                # Retry once
                crossref_data = query_crossref(doi)
                if '_error' in crossref_data:
                    enrichment_log[filename] = {'status': 'error', 'error': error, 'ts': datetime.now().isoformat()}
                    stats['errors'] += 1
                    print(f"  >> Still failing: {crossref_data.get('_error')}")
                    continue
            elif error == 'not_found':
                enrichment_log[filename] = {'status': 'not_found', 'ts': datetime.now().isoformat()}
                stats['not_found'] += 1
                print(f"  >> DOI not found on CrossRef")
                continue
            else:
                enrichment_log[filename] = {'status': 'error', 'error': error, 'ts': datetime.now().isoformat()}
                stats['errors'] += 1
                print(f"  >> Error: {error}")
                continue

        # Apply enrichment
        updated_fields = apply_enrichment(metadata[filename], crossref_data)

        if updated_fields:
            stats['enriched'] += 1
            for field in updated_fields:
                stats['fields_filled'][field] = stats['fields_filled'].get(field, 0) + 1
            enrichment_log[filename] = {'status': 'enriched', 'fields': updated_fields, 'ts': datetime.now().isoformat()}
            print(f"  OK Updated: {', '.join(updated_fields)}")
        else:
            stats['no_new_data'] += 1
            enrichment_log[filename] = {'status': 'no_new_data', 'ts': datetime.now().isoformat()}
            print(f"  -- No new data from CrossRef")

        save_counter += 1

        # Save progress every 25 papers
        if save_counter >= 25:
            elapsed = time.time() - start_time
            rate = idx / elapsed * 60
            print(f"\n  [SAVE] Saving progress ({idx} done, {rate:.0f} papers/min)...")
            with open(METADATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(enrichment_log, f, indent=2)
            save_counter = 0

        # Rate limiting
        time.sleep(args.delay)

    # Final save
    print("\n" + "=" * 70)
    print("Saving final results...")
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(enrichment_log, f, indent=2)

    # Summary
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("ENRICHMENT COMPLETE")
    print("=" * 70)
    print(f"Time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"Papers processed: {len(candidates)}")
    print(f"  Enriched: {stats['enriched']}")
    print(f"  No new data: {stats['no_new_data']}")
    print(f"  Not found on CrossRef: {stats['not_found']}")
    print(f"  Errors: {stats['errors']}")
    if stats['rate_limited']:
        print(f"  Rate limited: {stats['rate_limited']}")
    print(f"\nFields filled:")
    for field, count in sorted(stats['fields_filled'].items(), key=lambda x: -x[1]):
        print(f"  {field}: {count}")


if __name__ == "__main__":
    main()
