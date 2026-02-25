"""Detailed paper metadata tally."""
import sys
sys.path.insert(0, '.')
from lib.db import get_session
from lib.models import Paper
from lib.crossref import _present

with get_session() as s:
    papers = s.query(Paper).filter(Paper.deleted_at.is_(None)).all()
    total = len(papers)
    
    complete = 0
    partial = 0
    minimal = 0
    
    for p in papers:
        has_authors = bool(p.authors and len(p.authors) > 0)
        has_year = _present(p.year)
        has_journal = _present(p.journal)
        has_abstract = _present(p.abstract)
        has_title = _present(p.title)
        has_doi = bool(p.doi)
        
        core = int(has_authors) + int(has_year) + int(has_journal)
        extra = int(has_abstract) + int(has_doi)
        
        if core == 3 and extra >= 1:
            complete += 1
        elif core >= 2 or (core >= 1 and extra >= 1):
            partial += 1
        else:
            minimal += 1
    
    print(f"Total papers: {total}")
    print(f"Complete (authors+year+journal + abstract/doi): {complete}")
    print(f"Partial (some core metadata): {partial}")
    print(f"Minimal (title only or less): {minimal}")
    print()
    
    no_authors = sum(1 for p in papers if not p.authors or len(p.authors) == 0)
    no_year = sum(1 for p in papers if not _present(p.year))
    no_journal = sum(1 for p in papers if not _present(p.journal))
    no_abstract = sum(1 for p in papers if not _present(p.abstract))
    no_doi = sum(1 for p in papers if not p.doi)
    no_title = sum(1 for p in papers if not _present(p.title))
    verified = sum(1 for p in papers if p.crossref_verified)
    
    print("Missing field counts:")
    print(f"  No authors:  {no_authors}")
    print(f"  No year:     {no_year}")
    print(f"  No journal:  {no_journal}")
    print(f"  No abstract: {no_abstract}")
    print(f"  No DOI:      {no_doi}")
    print(f"  No title:    {no_title}")
    print(f"  CrossRef verified: {verified}")
