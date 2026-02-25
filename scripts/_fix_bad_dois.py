"""Fix papers that have ISSNs stored as DOIs and other bad DOI patterns."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.db import get_session
from lib.models import Paper
from lib.db_operations import upsert_paper

# Known bad DOI patterns (actually ISSNs or other non-DOI identifiers)
BAD_DOI_PATTERNS = [
    '10.1149/issn.',    # ISSN stored as DOI
    '10.1016/issn.',
]

def main():
    with get_session() as session:
        papers = session.query(Paper).filter(
            Paper.doi.isnot(None),
            Paper.deleted_at.is_(None)
        ).all()
        
        bad_papers = []
        for p in papers:
            doi = p.doi.strip() if p.doi else ''
            for pattern in BAD_DOI_PATTERNS:
                if doi.startswith(pattern):
                    bad_papers.append({
                        'filename': p.filename,
                        'doi': p.doi,
                        'title': (p.title or '')[:70],
                        'source_url': p.source_url or '',
                    })
                    break
        
        print(f"Found {len(bad_papers)} papers with bad DOIs:")
        for bp in bad_papers:
            print(f"  {bp['filename']}: DOI={bp['doi']}")
            print(f"    Title: {bp['title']}")
            print(f"    URL: {bp['source_url']}")
        
        if bad_papers and '--fix' in sys.argv:
            print(f"\nClearing bad DOIs for {len(bad_papers)} papers...")
            for bp in bad_papers:
                upsert_paper(bp['filename'], {'doi': None})
                print(f"  Cleared DOI for {bp['filename']}")
            print("Done! Papers can now be enriched via URL or title lookup.")
        elif bad_papers:
            print("\nRun with --fix to clear these bad DOIs")

if __name__ == "__main__":
    main()
