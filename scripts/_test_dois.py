"""Quick test of specific DOIs against CrossRef."""
import sys
sys.path.insert(0, '.')
from lib.crossref import query_crossref

test_dois = [
    '10.1038/sdata201920',
    '10.1109/ACCESS.2019.2940846',
    '10.1073/pnas.242483812',
    '10.1038/s41597-019-0020-z',  # alternate nature format
]

for doi in test_dois:
    r = query_crossref(doi)
    if r:
        title = r.get('title', '?')
        print(f"OK:   {doi}")
        print(f"      -> {title[:70]}")
    else:
        print(f"FAIL: {doi}")
