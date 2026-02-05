#!/usr/bin/env python3
"""
Normalize chemistry values in existing papers.

This script:
1. Reads metadata.json
2. Normalizes chemistry lists using the canonical taxonomy
3. Updates metadata.json with normalized values
4. Updates ChromaDB chunks with normalized comma-separated strings
5. Provides detailed statistics and dry-run mode

Usage:
    python scripts/normalize_chemistries.py --dry-run  # Preview changes
    python scripts/normalize_chemistries.py            # Apply normalization
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path so we can import from lib
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.chemistry_taxonomy import normalize_chemistries
import chromadb


def normalize_existing_papers(dry_run=False):
    """Normalize chemistry values in metadata.json and ChromaDB."""
    print("="*60)
    print("Chemistry Normalization Migration")
    if dry_run:
        print("DRY RUN MODE - No changes will be saved")
    print("="*60)
    print()

    # Load metadata.json
    metadata_file = Path("data/metadata.json")
    if not metadata_file.exists():
        print("ERROR: metadata.json not found")
        return

    with open(metadata_file, 'r', encoding='utf-8') as f:
        all_metadata = json.load(f)

    print(f"Found {len(all_metadata)} papers to normalize")

    # Connect to ChromaDB
    print("Connecting to ChromaDB...")
    client = chromadb.PersistentClient(path="data/chroma_db")
    try:
        collection = client.get_collection(name="battery_papers")
    except Exception as e:
        print(f"ERROR: Could not connect to ChromaDB: {e}")
        return

    print(f"Connected to ChromaDB collection with {collection.count()} chunks\n")

    # Track statistics
    stats = {
        'total_papers': len(all_metadata),
        'papers_changed': 0,
        'papers_unchanged': 0,
        'chemistries_before': {},  # chemistry -> count
        'chemistries_after': {},   # chemistry -> count
        'examples': {}             # old -> new examples
    }

    # Process each paper
    for idx, (filename, paper_meta) in enumerate(all_metadata.items(), 1):
        old_chemistries = paper_meta.get('chemistries', [])

        # Track old values
        for chem in old_chemistries:
            stats['chemistries_before'][chem] = stats['chemistries_before'].get(chem, 0) + 1

        # Normalize
        new_chemistries = normalize_chemistries(old_chemistries)

        # Track new values
        for chem in new_chemistries:
            stats['chemistries_after'][chem] = stats['chemistries_after'].get(chem, 0) + 1

        # Check if changed
        if set(old_chemistries) != set(new_chemistries):
            stats['papers_changed'] += 1

            # Store example mapping (limit to 10)
            old_str = ', '.join(old_chemistries)
            new_str = ', '.join(new_chemistries)
            if len(stats['examples']) < 10:
                stats['examples'][old_str] = new_str

            print(f"[{idx}/{stats['total_papers']}] {filename}:")
            print(f"  Old: {old_chemistries}")
            print(f"  New: {new_chemistries}")

            if not dry_run:
                # Update metadata.json
                paper_meta['chemistries'] = new_chemistries

                # Update ChromaDB chunks
                try:
                    results = collection.get(where={"filename": filename})
                    if results['ids']:
                        for i, chunk_id in enumerate(results['ids']):
                            existing_meta = results['metadatas'][i]
                            existing_meta['chemistries'] = ','.join(new_chemistries)
                            collection.update(
                                ids=[chunk_id],
                                metadatas=[existing_meta]
                            )
                        print(f"  [OK] Updated {len(results['ids'])} chunks in ChromaDB")
                    else:
                        print(f"  - No chunks found in ChromaDB")
                except Exception as e:
                    print(f"  ✗ ChromaDB update error: {e}")
        else:
            stats['papers_unchanged'] += 1

    # Save metadata.json
    if not dry_run and stats['papers_changed'] > 0:
        print(f"\nSaving updated metadata.json...")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, indent=2, ensure_ascii=False)
        print(f"[OK] Saved metadata.json")

    # Print statistics
    print(f"\n{'='*60}")
    print("Migration Statistics")
    print(f"{'='*60}")
    print(f"Total papers: {stats['total_papers']}")
    print(f"Papers changed: {stats['papers_changed']}")
    print(f"Papers unchanged: {stats['papers_unchanged']}")

    if stats['chemistries_before']:
        print(f"\n--- Chemistry Values BEFORE ---")
        for chem, count in sorted(stats['chemistries_before'].items()):
            print(f"  {chem}: {count} paper(s)")

    if stats['chemistries_after']:
        print(f"\n--- Chemistry Values AFTER ---")
        for chem, count in sorted(stats['chemistries_after'].items()):
            print(f"  {chem}: {count} paper(s)")

    if stats['examples']:
        print(f"\n--- Example Mappings ---")
        for old, new in stats['examples'].items():
            print(f"  {old} -> {new}")

    if dry_run:
        print(f"\nDRY RUN COMPLETE - Run without --dry-run to apply changes")
    else:
        if stats['papers_changed'] > 0:
            print(f"\n[OK] MIGRATION COMPLETE - {stats['papers_changed']} papers updated")
        else:
            print(f"\n[OK] MIGRATION COMPLETE - No changes needed")
    print()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Normalize chemistry values in paper database')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without saving')
    args = parser.parse_args()

    try:
        normalize_existing_papers(dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
