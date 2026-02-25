"""Test scrape_doi_from_page on real publisher URLs."""
import sys
sys.path.insert(0, '.')
from lib.crossref import scrape_doi_from_page, extract_doi_from_url

test_urls = [
    'https://www.mdpi.com/2313-0105/7/4/88',
    'https://www.mdpi.com/1996-1073/14/4/1206',
    'https://ieeexplore.ieee.org/document/9508451',
    'https://arxiv.org/abs/2301.09831',
    'https://www.sciencedirect.com/science/article/pii/S2352152X21012585',
    'https://www.frontiersin.org/articles/10.3389/fenrg.2022.1059126/full',
]

for url in test_urls:
    # First try URL extraction
    doi = extract_doi_from_url(url)
    if doi:
        print(f"URL extract: {url[:50]}... -> {doi}")
    else:
        # Try scraping
        doi = scrape_doi_from_page(url)
        if doi:
            print(f"Scraped:     {url[:50]}... -> {doi}")
        else:
            print(f"FAILED:      {url[:50]}...")
