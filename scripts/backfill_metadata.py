#!/usr/bin/env python3
"""
Backfill existing papers with new metadata fields.

This script:
1. Reads metadata.json
2. For each paper with a DOI, queries CrossRef for new fields
3. Updates metadata.json and ChromaDB chunks
4. Sets default values for fields that can't be backfilled
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path so we can import from app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import query_crossref_for_metadata
import chromadb


def backfill_existing_papers():
    """Update existing papers with new metadata fields."""
    print("="*60)
    print("Backfilling Metadata for Existing Papers")
    print("="*60)

    # Load metadata.json
    metadata_file = Path("data/metadata.json")
    if not metadata_file.exists():
        print("ERROR: metadata.json not found")
        return

    with open(metadata_file, 'r', encoding='utf-8') as f:
        all_metadata = json.load(f)

    print(f"\nFound {len(all_metadata)} papers to update")

    # Connect to ChromaDB
    print("Connecting to ChromaDB...")
    client = chromadb.PersistentClient(path="data/chroma_db")
    try:
        collection = client.get_collection(name="papers")
    except Exception as e:
        print(f"ERROR: Could not connect to ChromaDB: {e}")
        return

    print(f"Connected to ChromaDB collection with {collection.count()} chunks\n")

    # Track statistics
    updated_count = 0
    crossref_success = 0
    crossref_fail = 0

    for filename, paper_meta in all_metadata.items():
        print(f"\n[{updated_count + 1}/{len(all_metadata)}] Processing: {filename}")

        # Add date_added if missing (use extracted_at or current time)
        if 'date_added' not in paper_meta:
            paper_meta['date_added'] = paper_meta.get('extracted_at', datetime.now().isoformat())
            print(f"  ✓ Set date_added")

        # Query CrossRef if DOI exists
        doi = paper_meta.get('doi')
        if doi:
            print(f"  Querying CrossRef for DOI: {doi}")
            try:
                crossref_data = query_crossref_for_metadata(doi)
                if crossref_data:
                    # Update fields from CrossRef
                    paper_meta['abstract'] = crossref_data.get('abstract', '')
                    paper_meta['author_keywords'] = crossref_data.get('author_keywords', [])
                    paper_meta['volume'] = crossref_data.get('volume', '')
                    paper_meta['issue'] = crossref_data.get('issue', '')
                    paper_meta['pages'] = crossref_data.get('pages', '')
                    paper_meta['references'] = crossref_data.get('references', [])

                    fields_found = []
                    if paper_meta['abstract']: fields_found.append('abstract')
                    if paper_meta['author_keywords']: fields_found.append('keywords')
                    if paper_meta['volume']: fields_found.append('volume')
                    if paper_meta['issue']: fields_found.append('issue')
                    if paper_meta['pages']: fields_found.append('pages')
                    if paper_meta['references']: fields_found.append('references')

                    if fields_found:
                        print(f"  ✓ CrossRef data: {', '.join(fields_found)}")
                    else:
                        print(f"  ⚠ CrossRef returned no new data")

                    crossref_success += 1
                else:
                    print(f"  ✗ CrossRef query returned empty")
                    crossref_fail += 1
            except Exception as e:
                print(f"  ✗ CrossRef error: {e}")
                crossref_fail += 1
        else:
            print(f"  - No DOI, skipping CrossRef")

        # Set defaults for fields that can't be backfilled
        paper_meta.setdefault('source_url', '')
        paper_meta.setdefault('notes', '')
        paper_meta.setdefault('abstract', '')
        paper_meta.setdefault('author_keywords', [])
        paper_meta.setdefault('volume', '')
        paper_meta.setdefault('issue', '')
        paper_meta.setdefault('pages', '')
        paper_meta.setdefault('references', [])

        # Update ChromaDB chunks for this paper
        print(f"  Updating ChromaDB chunks...")
        try:
            results = collection.get(where={"filename": filename})
            if results['ids']:
                # Update each chunk's metadata
                for i, chunk_id in enumerate(results['ids']):
                    # Get existing metadata
                    existing_meta = results['metadatas'][i]

                    # Add new fields
                    existing_meta['abstract'] = paper_meta.get('abstract', '')
                    existing_meta['author_keywords'] = ';'.join(paper_meta.get('author_keywords', []))
                    existing_meta['volume'] = paper_meta.get('volume', '')
                    existing_meta['issue'] = paper_meta.get('issue', '')
                    existing_meta['pages'] = paper_meta.get('pages', '')
                    existing_meta['date_added'] = paper_meta.get('date_added', '')
                    existing_meta['source_url'] = paper_meta.get('source_url', '')

                    # Update the chunk
                    collection.update(
                        ids=[chunk_id],
                        metadatas=[existing_meta]
                    )

                print(f"  ✓ Updated {len(results['ids'])} chunks")
            else:
                print(f"  - No chunks found in ChromaDB")
        except Exception as e:
            print(f"  ✗ ChromaDB update error: {e}")

        updated_count += 1

    # Save updated metadata.json
    print(f"\nSaving updated metadata.json...")
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print("Backfill Complete!")
    print(f"{'='*60}")
    print(f"Papers updated: {updated_count}")
    print(f"CrossRef success: {crossref_success}")
    print(f"CrossRef failed: {crossref_fail}")
    print()


if __name__ == '__main__':
    try:
        backfill_existing_papers()
    except KeyboardInterrupt:
        print("\n\nBackfill interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
