"""Analyze what types of papers still need enrichment."""
import sys, re
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.db import get_session
from lib.models import Paper
from lib.crossref import _present

def main():
    with get_session() as session:
        papers = session.query(Paper).filter(Paper.deleted_at.is_(None)).all()
        
        incomplete = []
        for p in papers:
            missing_authors = not p.authors or len(p.authors) == 0
            missing_year = not _present(p.year)
            missing_journal = not _present(p.journal)
            if missing_authors or missing_year or missing_journal:
                incomplete.append(p)
        
        print(f"Total incomplete: {len(incomplete)}")
        
        # Categorize by URL domain
        url_domains = Counter()
        for p in incomplete:
            url = p.source_url or ''
            if url:
                m = re.search(r'https?://([^/]+)', url)
                if m:
                    domain = m.group(1).replace('www.', '')
                    url_domains[domain] += 1
        
        print(f"\nURL domains of incomplete papers:")
        for domain, count in url_domains.most_common(30):
            print(f"  {domain}: {count}")
        
        # Count missing fields
        no_authors = sum(1 for p in incomplete if not p.authors or len(p.authors) == 0)
        no_year = sum(1 for p in incomplete if not _present(p.year))
        no_journal = sum(1 for p in incomplete if not _present(p.journal))
        no_title = sum(1 for p in incomplete if not _present(p.title))
        no_abstract = sum(1 for p in incomplete if not _present(p.abstract))
        has_doi = sum(1 for p in incomplete if p.doi)
        
        print(f"\nMissing field stats:")
        print(f"  No authors: {no_authors}")
        print(f"  No year: {no_year}")
        print(f"  No journal: {no_journal}")
        print(f"  No title: {no_title}")
        print(f"  No abstract: {no_abstract}")
        print(f"  Has DOI: {has_doi}")
        
        # Papers with good titles but missing other fields
        has_title_no_journal = sum(1 for p in incomplete 
            if _present(p.title) and not _present(p.journal) and not p.doi)
        print(f"\n  Has title, no journal, no DOI: {has_title_no_journal}")
        
        # Show sample of MDPI papers
        mdpi = [p for p in incomplete if p.source_url and 'mdpi.com' in p.source_url]
        print(f"\nMDPI papers still incomplete: {len(mdpi)}")
        for p in mdpi[:5]:
            title = (p.title or '')[:60]
            print(f"  {p.filename}: {title}")
            print(f"    URL: {p.source_url}")

if __name__ == "__main__":
    main()
