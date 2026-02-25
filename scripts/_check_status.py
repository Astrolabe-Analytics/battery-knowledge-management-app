import requests, json
r = requests.get('http://localhost:8003/api/import/enrich/status')
d = r.json()
print(f"Complete: {d['complete']}, Needs: {d['needs_enrichment']}")
print(f"  DOI: {d['breakdown']['has_doi']}, URL: {d['breakdown']['has_url']}, Title: {d['breakdown']['has_title_only']}")
print(f"  CrossRef verified: {d['crossref_verified']}")
