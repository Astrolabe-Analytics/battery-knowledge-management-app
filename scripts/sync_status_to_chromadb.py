"""
Sync pdf_status from metadata.json to ChromaDB
Updates ChromaDB's stored metadata to match metadata.json
"""

import json
import chromadb
from pathlib import Path
from tqdm import tqdm

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"
CHROMA_DB_PATH = BASE_DIR / "data" / "chroma_db"

def main():
    print("Syncing pdf_status from metadata.json to ChromaDB...")
    print("=" * 60)

    # Load metadata.json
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    print(f"Loaded {len(metadata)} papers from metadata.json")

    # Connect to ChromaDB
    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    collection = client.get_collection('battery_papers')

    # Get all chunks from ChromaDB
    result = collection.get(include=['metadatas'])
    print(f"Found {len(result['ids'])} chunks in ChromaDB")

    # Update each chunk's metadata
    print("\nUpdating ChromaDB metadata...")
    updated_count = 0
    chunks_by_file = {}

    # Group chunks by filename
    for i, chunk_id in enumerate(result['ids']):
        chunk_meta = result['metadatas'][i]
        filename = chunk_meta.get('filename')
        if filename:
            if filename not in chunks_by_file:
                chunks_by_file[filename] = []
            chunks_by_file[filename].append((chunk_id, chunk_meta))

    # Update each file's chunks
    for filename, chunks in tqdm(chunks_by_file.items(), desc="Updating files"):
        if filename in metadata:
            # Get new status from metadata.json
            new_status = metadata[filename].get('pdf_status', 'unknown')
            metadata_incomplete = metadata[filename].get('metadata_incomplete', False)
            crossref_verified = metadata[filename].get('crossref_verified', False)

            # Update all chunks for this file
            for chunk_id, old_meta in chunks:
                # Update metadata
                updated_meta = old_meta.copy()
                updated_meta['pdf_status'] = new_status
                updated_meta['metadata_incomplete'] = metadata_incomplete
                updated_meta['crossref_verified'] = crossref_verified

                # Update in ChromaDB
                collection.update(
                    ids=[chunk_id],
                    metadatas=[updated_meta]
                )

            updated_count += 1

    print(f"\nUpdated {updated_count} files in ChromaDB")
    print("\n" + "=" * 60)
    print("SYNC COMPLETE!")
    print("=" * 60)
    print("Restart the Streamlit UI to see updated stats")

if __name__ == "__main__":
    main()
