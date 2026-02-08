"""
ChromaDB Cleanup Script
Removes entries for invalid PDFs (moved to papers_invalid/) from ChromaDB
"""

import chromadb
import json
from pathlib import Path
from typing import Set, List

# Paths
BASE_DIR = Path(__file__).parent.parent
PAPERS_DIR = BASE_DIR / "papers"
INVALID_DIR = BASE_DIR / "papers_invalid"
CHROMA_DB_PATH = BASE_DIR / "data" / "chroma_db"
METADATA_FILE = BASE_DIR / "data" / "metadata.json"

def get_invalid_pdf_filenames() -> Set[str]:
    """Get list of filenames in papers_invalid/"""
    return {f.name for f in INVALID_DIR.glob("*.pdf")}

def get_chromadb_chunks_for_files(collection, filenames: Set[str]) -> List[str]:
    """Get all chunk IDs for papers with given filenames"""
    # Get all data from collection
    result = collection.get(include=['metadatas'])

    chunk_ids_to_delete = []
    for i, metadata in enumerate(result['metadatas']):
        if metadata.get('filename') in filenames:
            chunk_ids_to_delete.append(result['ids'][i])

    return chunk_ids_to_delete

def main():
    print("ChromaDB Invalid Entry Cleanup")
    print("=" * 60)

    # Get invalid filenames
    invalid_filenames = get_invalid_pdf_filenames()
    print(f"\nInvalid PDFs to remove: {len(invalid_filenames)}")

    if not invalid_filenames:
        print("No invalid PDFs found. Nothing to clean up.")
        return

    # Connect to ChromaDB
    print(f"\nConnecting to ChromaDB at {CHROMA_DB_PATH}...")
    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    collection = client.get_collection('battery_papers')

    # Get current stats
    total_chunks_before = collection.count()
    print(f"Total chunks before cleanup: {total_chunks_before}")

    # Find chunks to delete
    print(f"\nFinding chunks for {len(invalid_filenames)} invalid papers...")
    chunk_ids_to_delete = get_chromadb_chunks_for_files(collection, invalid_filenames)

    print(f"Chunks to delete: {len(chunk_ids_to_delete)}")

    if not chunk_ids_to_delete:
        print("\nNo chunks found for invalid papers. ChromaDB is already clean!")
        return

    # Show sample of what will be deleted
    print(f"\nSample of papers to be removed from ChromaDB:")
    sample_filenames = list(invalid_filenames)[:10]
    for filename in sample_filenames:
        print(f"  - {filename}")
    if len(invalid_filenames) > 10:
        print(f"  ... and {len(invalid_filenames) - 10} more")

    # Confirm deletion
    print(f"\nThis will delete {len(chunk_ids_to_delete)} chunks from ChromaDB.")
    print("This action cannot be undone (unless you restore from backup).")
    response = input("\nProceed with cleanup? (yes/no): ").strip().lower()

    if response != 'yes':
        print("Cleanup cancelled.")
        return

    # Delete chunks in batches
    print(f"\nDeleting {len(chunk_ids_to_delete)} chunks...")
    batch_size = 1000
    deleted_count = 0

    for i in range(0, len(chunk_ids_to_delete), batch_size):
        batch = chunk_ids_to_delete[i:i + batch_size]
        collection.delete(ids=batch)
        deleted_count += len(batch)
        print(f"  Deleted {deleted_count}/{len(chunk_ids_to_delete)} chunks...")

    # Get final stats
    total_chunks_after = collection.count()
    print(f"\nTotal chunks after cleanup: {total_chunks_after}")
    print(f"Chunks removed: {total_chunks_before - total_chunks_after}")

    # Verify cleanup
    print("\nVerifying cleanup...")
    remaining_invalid = get_chromadb_chunks_for_files(collection, invalid_filenames)
    if remaining_invalid:
        print(f"WARNING: {len(remaining_invalid)} chunks for invalid papers still remain!")
    else:
        print("✓ All invalid paper entries successfully removed from ChromaDB")

    # Show final stats
    print("\n" + "=" * 60)
    print("CLEANUP COMPLETE")
    print("=" * 60)
    print(f"Chunks before: {total_chunks_before}")
    print(f"Chunks after:  {total_chunks_after}")
    print(f"Chunks removed: {total_chunks_before - total_chunks_after}")

    # Get unique papers remaining
    result = collection.get(include=['metadatas'])
    remaining_filenames = set()
    for metadata in result['metadatas']:
        if 'filename' in metadata:
            remaining_filenames.add(metadata['filename'])

    print(f"\nUnique papers remaining in ChromaDB: {len(remaining_filenames)}")

    # Check against valid PDFs
    valid_pdfs = {f.name for f in PAPERS_DIR.glob("*.pdf")}
    papers_with_valid_pdfs = len([f for f in remaining_filenames if f in valid_pdfs])

    print(f"Papers with valid PDFs on disk: {papers_with_valid_pdfs}")
    print(f"Papers without PDFs (metadata-only): {len(remaining_filenames) - papers_with_valid_pdfs}")

if __name__ == "__main__":
    main()
