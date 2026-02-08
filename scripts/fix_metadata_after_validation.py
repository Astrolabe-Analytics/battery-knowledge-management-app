"""
Fix metadata.json after moving invalid PDFs to papers_invalid/
Marks moved papers as metadata_only
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"
INVALID_DIR = BASE_DIR / "papers_invalid"

# Load metadata
with open(METADATA_FILE, 'r', encoding='utf-8') as f:
    metadata = json.load(f)

print(f"Total papers in metadata: {len(metadata)}")

# Get list of moved PDFs
moved_pdfs = [f.name for f in INVALID_DIR.glob("*.pdf")]
print(f"Invalid PDFs moved: {len(moved_pdfs)}")

# Update metadata for moved PDFs
updated_count = 0
for filename in moved_pdfs:
    if filename in metadata:
        # Mark as metadata_only
        metadata[filename]['pdf_status'] = 'metadata_only'
        metadata[filename].pop('pdf_source', None)
        metadata[filename].pop('pdf_downloaded_at', None)
        updated_count += 1

print(f"Updated {updated_count} papers in metadata")

# Save updated metadata
with open(METADATA_FILE, 'w', encoding='utf-8') as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)

print(f"Metadata saved to {METADATA_FILE}")

# Count paper statuses
status_counts = {}
for filename, paper in metadata.items():
    status = paper.get('pdf_status', 'unknown')
    status_counts[status] = status_counts.get(status, 0) + 1

print("\nPaper status distribution:")
for status, count in sorted(status_counts.items()):
    print(f"  {status}: {count}")
