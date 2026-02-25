"""
Backfill missing DOIs for paper references using CrossRef title search.

Usage:
    python scripts/backfill_ref_dois.py [--limit N] [--delay SECS] [--dry-run]
"""
import argparse
import time
import requests
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.db import get_raw_connection

def normalize(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    s = s.lower()
    s = re.sub(r'[^\w\s]', '', s)
    return re.sub(r'\s+', ' ', s).strip()

def titles_match(a: str, b: str) -> bool:
    """Check if two titles are close enough (exact normalized match)."""
    return normalize(a) == normalize(b)

def search_crossref_doi(title: str, author: str = "", year: str = "") -> str | None:
    """Query CrossRef for a DOI by title. Return DOI if confident match."""
    query = title
    if author:
        query += f" {author}"
    
    url = "https://api.crossref.org/works"
    params = {
        "query.bibliographic": query,
        "rows": 3,
        "select": "DOI,title",
    }
    headers = {"User-Agent": "AstrolabeLibrary/1.0 (mailto:researcher@example.com)"}
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        
        items = resp.json().get("message", {}).get("items", [])
        for item in items:
            cr_titles = item.get("title", [])
            for cr_title in cr_titles:
                if titles_match(title, cr_title):
                    return item.get("DOI")
        return None
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Backfill missing DOIs for references")
    parser.add_argument("--limit", type=int, default=500, help="Max refs to process")
    parser.add_argument("--delay", type=float, default=0.15, help="Delay between API calls (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Don't update DB, just print")
    args = parser.parse_args()

    conn = get_raw_connection()
    cur = conn.cursor()

    # Get references with title but no DOI
    cur.execute("""
        SELECT pr.id, pr.article_title, pr.author, pr.year
        FROM paper_references pr
        JOIN papers p ON pr.paper_filename = p.filename
        WHERE p.deleted_at IS NULL
          AND (pr.doi = '' OR pr.doi IS NULL)
          AND pr.article_title != ''
          AND pr.article_title IS NOT NULL
        ORDER BY pr.id
        LIMIT %s
    """, (args.limit,))
    refs = cur.fetchall()
    print(f"Processing {len(refs)} references without DOIs...")

    found = 0
    not_found = 0
    errors = 0

    for i, (ref_id, title, author, year) in enumerate(refs):
        if i > 0 and i % 50 == 0:
            print(f"  Progress: {i}/{len(refs)} (found {found} DOIs so far)")

        doi = search_crossref_doi(title, author or "", year or "")
        
        if doi:
            found += 1
            print(f"  FOUND [{ref_id}] {title[:60]} -> {doi}")
            if not args.dry_run:
                cur.execute("UPDATE paper_references SET doi = %s WHERE id = %s", (doi, ref_id))
        else:
            not_found += 1

        time.sleep(args.delay)

    if not args.dry_run:
        conn.commit()
    conn.close()

    print(f"\nDone! Processed {len(refs)} refs:")
    print(f"  Found DOI: {found}")
    print(f"  Not found: {not_found}")
    if args.dry_run:
        print("  (dry run — no changes saved)")


if __name__ == "__main__":
    main()
