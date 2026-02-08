"""
Enrich all incomplete and metadata-only papers using Semantic Scholar and CrossRef APIs.
Runs unattended with progress reporting.
"""
import json
import time
from pathlib import Path
from typing import Dict, List
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.app_helpers import find_doi_via_semantic_scholar, query_crossref_for_metadata

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"

def load_metadata():
    """Load metadata.json"""
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_metadata(metadata):
    """Save metadata.json"""
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

def main():
    print("=" * 70)
    print("ENRICHING ALL INCOMPLETE AND METADATA-ONLY PAPERS")
    print("=" * 70)
    print("This will attempt to find missing metadata using:")
    print("  1. Semantic Scholar API (to find DOIs)")
    print("  2. CrossRef API (to get full metadata)")
    print()

    # Load metadata
    print("Loading metadata.json...")
    metadata = load_metadata()
    total_papers = len(metadata)
    print(f"Total papers: {total_papers}")

    # Filter to incomplete and metadata-only papers
    papers_to_enrich = []
    for filename, paper in metadata.items():
        pdf_status = paper.get('pdf_status', '').lower()
        if pdf_status in ['incomplete', 'metadata_only']:
            # Only enrich if missing DOI or missing critical metadata
            has_doi = bool(paper.get('doi', '').strip())
            has_authors = bool(paper.get('authors'))
            has_year = bool(paper.get('year'))
            has_journal = bool(paper.get('journal', '').strip())

            if not has_doi or not has_authors or not has_year or not has_journal:
                papers_to_enrich.append({
                    'filename': filename,
                    'title': paper.get('title', filename.replace('.pdf', '')),
                    'has_doi': has_doi,
                    'missing_fields': []
                })

                # Track what's missing
                if not has_doi:
                    papers_to_enrich[-1]['missing_fields'].append('DOI')
                if not has_authors:
                    papers_to_enrich[-1]['missing_fields'].append('authors')
                if not has_year:
                    papers_to_enrich[-1]['missing_fields'].append('year')
                if not has_journal:
                    papers_to_enrich[-1]['missing_fields'].append('journal')

    print(f"\nPapers to enrich: {len(papers_to_enrich)}")
    print(f"  - Incomplete: {len([p for p in papers_to_enrich if metadata[p['filename']].get('pdf_status') == 'incomplete'])}")
    print(f"  - Metadata-only: {len([p for p in papers_to_enrich if metadata[p['filename']].get('pdf_status') == 'metadata_only'])}")
    print()

    if len(papers_to_enrich) == 0:
        print("No papers need enrichment!")
        return

    # Enrich papers
    print("Starting enrichment process...")
    print("=" * 70)

    found_doi_count = 0
    enriched_count = 0
    failed_count = 0
    skipped_count = 0

    for idx, paper_info in enumerate(papers_to_enrich, 1):
        filename = paper_info['filename']
        title = paper_info['title']
        has_doi = paper_info['has_doi']

        # Progress indicator
        progress_pct = (idx / len(papers_to_enrich)) * 100
        # Sanitize title for console output (replace non-ASCII chars)
        safe_title = title[:80].encode('ascii', 'replace').decode('ascii')
        print(f"\n[{idx}/{len(papers_to_enrich)} - {progress_pct:.1f}%] {filename}")
        print(f"  Title: {safe_title}...")
        print(f"  Missing: {', '.join(paper_info['missing_fields'])}")

        doi_to_use = metadata[filename].get('doi', '')

        # Step 1: Find DOI if missing
        if not has_doi:
            print(f"  -> Finding DOI via Semantic Scholar...")
            found_doi = find_doi_via_semantic_scholar(title)
            if found_doi:
                doi_to_use = found_doi
                found_doi_count += 1
                print(f"  OK Found DOI: {found_doi}")
            else:
                print(f"  X DOI not found")
                failed_count += 1
                continue
        else:
            doi_to_use = metadata[filename].get('doi', '')
            print(f"  OK Has DOI: {doi_to_use}")

        # Step 2: Enrich from CrossRef
        if doi_to_use:
            print(f"  -> Querying CrossRef for metadata...")
            crossref_data = query_crossref_for_metadata(doi_to_use)

            if crossref_data:
                # Update metadata
                updated = False

                if not has_doi:
                    metadata[filename]['doi'] = doi_to_use
                    updated = True

                if crossref_data.get('title') and not metadata[filename].get('title'):
                    metadata[filename]['title'] = crossref_data['title'][0] if isinstance(crossref_data['title'], list) else crossref_data['title']
                    updated = True

                if crossref_data.get('author'):
                    authors = []
                    for author in crossref_data['author']:
                        given = author.get('given', '')
                        family = author.get('family', '')
                        if family:
                            authors.append(f"{given} {family}".strip())
                    if authors:
                        metadata[filename]['authors'] = authors
                        updated = True

                if crossref_data.get('published'):
                    year = None
                    date_parts = crossref_data['published'].get('date-parts', [[]])[0]
                    if date_parts and len(date_parts) > 0:
                        year = str(date_parts[0])
                        metadata[filename]['year'] = year
                        updated = True

                if crossref_data.get('container-title'):
                    journal = crossref_data['container-title'][0] if isinstance(crossref_data['container-title'], list) else crossref_data['container-title']
                    if journal:
                        metadata[filename]['journal'] = journal
                        updated = True

                # Mark as CrossRef verified
                metadata[filename]['crossref_verified'] = True

                if updated:
                    enriched_count += 1
                    print(f"  OK Enriched with CrossRef data")
                else:
                    skipped_count += 1
                    print(f"  o No new data from CrossRef")
            else:
                failed_count += 1
                print(f"  X CrossRef query failed")

        # Save metadata every 10 papers
        if idx % 10 == 0:
            print(f"\n  [SAVE] Saving progress...")
            save_metadata(metadata)

        # Rate limiting - small delay between requests
        time.sleep(0.5)

    # Final save
    print("\n" + "=" * 70)
    print("Saving final results...")
    save_metadata(metadata)

    # Summary
    print("\n" + "=" * 70)
    print("ENRICHMENT COMPLETE")
    print("=" * 70)
    print(f"Total papers processed: {len(papers_to_enrich)}")
    print(f"  OK DOIs found: {found_doi_count}")
    print(f"  OK Successfully enriched: {enriched_count}")
    print(f"  o Skipped (no new data): {skipped_count}")
    print(f"  X Failed (not found): {failed_count}")
    print()
    print("Next steps:")
    print("  1. Run: python scripts/mark_incomplete_metadata.py")
    print("  2. Run: python scripts/sync_status_to_chromadb.py")
    print("  3. Restart the Streamlit UI")

if __name__ == "__main__":
    main()
