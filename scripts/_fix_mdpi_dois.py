"""
Fix MDPI papers with bad DOIs (URL-path format like 10.3390/2313-0105/10/5/152).
These are actually URL paths, not real DOIs. Clear them so title-based lookup can work.

Also fix other known bad DOI patterns (Nature /full suffix, Frontiers /full, etc.)
"""
import sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.db import get_session
from lib.models import Paper
from lib.db_operations import upsert_paper

# MDPI ISSN patterns that appear as bad DOIs
MDPI_ISSN_PATTERN = re.compile(r'^10\.3390/\d{4}-\d{4}/')
# Frontiers with /full suffix
FRONTIERS_FULL = re.compile(r'/full$')
# ECS with /meta suffix
ECS_META = re.compile(r'/meta$')


def is_bad_doi(doi):
    """Check if a DOI is actually a URL path or other non-standard format."""
    if not doi:
        return False
    doi = doi.strip()
    # MDPI URL-path format (10.3390/ISSN/vol/issue/page)
    if MDPI_ISSN_PATTERN.match(doi):
        return True
    # DOIs ending in /full (Frontiers, etc.)
    if doi.endswith('/full'):
        return True
    # DOIs ending in /meta
    if doi.endswith('/meta'):
        return True
    # DOIs that are actually ISSNs
    if '/issn.' in doi.lower():
        return True
    return False


def main():
    with get_session() as session:
        papers = session.query(Paper).filter(
            Paper.doi.isnot(None),
            Paper.deleted_at.is_(None)
        ).all()
        
        bad_papers = []
        for p in papers:
            if is_bad_doi(p.doi):
                bad_papers.append({
                    'filename': p.filename,
                    'doi': p.doi,
                    'title': (p.title or '')[:70],
                    'source_url': p.source_url or '',
                })
        
        print(f"Found {len(bad_papers)} papers with bad/non-standard DOIs:")
        for bp in bad_papers[:20]:
            print(f"  {bp['doi']}")
        if len(bad_papers) > 20:
            print(f"  ... and {len(bad_papers) - 20} more")
        
        if bad_papers and '--fix' in sys.argv:
            print(f"\nClearing bad DOIs for {len(bad_papers)} papers...")
            cleared = 0
            for bp in bad_papers:
                upsert_paper(bp['filename'], {'doi': None})
                cleared += 1
            print(f"Cleared {cleared} bad DOIs.")
            print("These papers will now be enriched via URL extraction or title lookup.")
        elif bad_papers:
            print(f"\nRun with --fix to clear these {len(bad_papers)} bad DOIs")

if __name__ == "__main__":
    main()
