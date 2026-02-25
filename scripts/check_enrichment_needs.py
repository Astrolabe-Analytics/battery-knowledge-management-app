"""Check which papers need enrichment and categorize them."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.db import get_session
from lib.models import Paper

PAPERS_DIR = Path(__file__).parent.parent / 'papers'

with get_session() as db:
    papers = db.query(Paper).filter(Paper.deleted_at.is_(None)).all()
    # detach from session
    for p in papers:
        db.expunge(p)

def _present(val):
    if not val: return False
    s = str(val).strip().lower()
    return s not in {'unknown', 'not specified', 'none', 'n/a', ''}

incomplete = []
no_doi = []
has_doi_incomplete = []

for p in papers:
    mc = all([_present(p.title), _present(p.authors), _present(p.year), _present(p.journal)])
    if not mc:
        incomplete.append(p)
        if _present(p.doi):
            has_doi_incomplete.append(p)
        else:
            no_doi.append(p)

total_active = len(papers)
print(f"Total active papers: {total_active}")
print(f"Incomplete metadata: {len(incomplete)}")
print(f"  - Has DOI (can enrich via CrossRef): {len(has_doi_incomplete)}")
print(f"  - No DOI (needs S2 lookup first): {len(no_doi)}")
print()

print("=== Has DOI but incomplete (first 15) ===")
for p in has_doi_incomplete[:15]:
    missing = []
    if not _present(p.title): missing.append('title')
    if not _present(p.authors): missing.append('authors')
    if not _present(p.year): missing.append('year')
    if not _present(p.journal): missing.append('journal')
    doi_str = p.doi[:40] if p.doi else "None"
    print(f"  {p.filename[:50]:50s} DOI={doi_str:40s} missing={missing}")

print()
print("=== No DOI, incomplete (first 15) ===")
for p in no_doi[:15]:
    missing = []
    if not _present(p.title): missing.append('title')
    if not _present(p.authors): missing.append('authors')
    if not _present(p.year): missing.append('year')
    if not _present(p.journal): missing.append('journal')
    title_str = str(p.title)[:60] if p.title else "None"
    print(f"  {p.filename[:50]:50s} title={title_str} missing={missing}")

# crossref_verified stats
verified = len([p for p in papers if p.crossref_verified])
print(f"\nCrossRef verified: {verified}/{total_active}")

# Papers with source_url that might contain a DOI
url_papers = [p for p in no_doi if _present(p.source_url)]
print(f"No DOI but has source_url: {len(url_papers)}")
for p in url_papers[:10]:
    url_s = p.source_url[:70] if p.source_url else "None"
    print(f"  fn={p.filename[:40]:42s} url={url_s}")

# Papers with title but missing DOI (could use S2)
titled_no_doi = [p for p in no_doi if _present(p.title)]
print(f"\nHas title but no DOI (S2 candidates): {len(titled_no_doi)}")
for p in titled_no_doi[:10]:
    print(f"  title={str(p.title)[:80]}")
