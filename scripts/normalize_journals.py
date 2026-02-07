"""
Normalize journal names across all papers in metadata.json.

Standardizes journal name variations to canonical full names.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.journal_normalizer import normalize_all_journals
from lib.rag import DatabaseClient


def main():
    print("=" * 80)
    print("Journal Name Normalization")
    print("=" * 80)
    print()

    # Load metadata
    metadata_file = Path("data/metadata.json")
    if not metadata_file.exists():
        print("[ERROR] metadata.json not found")
        return

    with open(metadata_file, 'r', encoding='utf-8') as f:
        all_metadata = json.load(f)

    print(f"Loaded {len(all_metadata)} papers from metadata.json")
    print()

    # Normalize journals
    print("Analyzing journal names...")
    updated_metadata, stats = normalize_all_journals(all_metadata)

    # Print statistics
    print()
    print("=" * 80)
    print("NORMALIZATION STATISTICS")
    print("=" * 80)
    print(f"Total papers:              {stats['total_papers']}")
    print(f"Papers with journal field: {stats['papers_with_journal']}")
    print(f"Papers normalized:         {stats['papers_normalized']}")
    print()

    if stats['papers_normalized'] == 0:
        print("[OK] No journals needed normalization!")
        return

    # Show before/after for each journal
    print("=" * 80)
    print("CHANGES BY JOURNAL")
    print("=" * 80)
    print()

    journal_summary = stats['journal_summary']
    for canonical_name in sorted(journal_summary.keys()):
        info = journal_summary[canonical_name]
        variations = sorted(info['variations'])
        count = info['count']

        print(f"[+] {canonical_name}")
        print(f"    Normalized {count} paper(s) from:")
        for variation in variations:
            variation_count = sum(1 for c in stats['changes']
                                if c['before'] == variation and c['after'] == canonical_name)
            print(f"      - \"{variation}\" ({variation_count} paper(s))")
        print()

    # Save updated metadata
    print("=" * 80)
    print("Saving changes...")
    print()

    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(updated_metadata, f, indent=2, ensure_ascii=False)

    print("[+] Saved metadata.json")

    # Update ChromaDB
    print("[+] Updating ChromaDB...")
    update_count = 0
    error_count = 0

    for change in stats['changes']:
        filename = change['filename']
        try:
            success = DatabaseClient.update_paper_metadata(filename, updated_metadata[filename])
            if success:
                update_count += 1
            else:
                error_count += 1
        except Exception as e:
            error_count += 1
            print(f"  [WARN] ChromaDB update failed for {filename}: {e}")

    print(f"[+] Updated {update_count} papers in ChromaDB")
    if error_count > 0:
        print(f"[WARN] {error_count} ChromaDB updates failed")

    # Clear caches
    DatabaseClient.clear_cache()
    print("[+] Cleared caches")

    print()
    print("=" * 80)
    print(f"[OK] Done! Normalized {stats['papers_normalized']} journal names.")
    print("     Restart the Streamlit app to see changes.")
    print("=" * 80)


if __name__ == "__main__":
    main()
