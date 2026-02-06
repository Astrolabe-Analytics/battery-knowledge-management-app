"""
Sync papers from metadata.json to ChromaDB
Adds missing papers to ChromaDB so they show up in the library
"""
import json
from pathlib import Path
from lib.rag import DatabaseClient

def sync_metadata_to_chromadb():
    """Add all papers from metadata.json to ChromaDB if they're missing."""

    # Load metadata.json
    metadata_file = Path("data/metadata.json")
    with open(metadata_file, 'r', encoding='utf-8') as f:
        all_metadata = json.load(f)

    # Get existing files in ChromaDB
    collection = DatabaseClient.get_collection()
    all_results = collection.get(include=["metadatas"])
    chromadb_files = set(m.get('filename', '') for m in all_results['metadatas'] if m.get('filename'))

    print(f"Papers in metadata.json: {len(all_metadata)}")
    print(f"Papers in ChromaDB: {len(chromadb_files)}")

    missing_files = set(all_metadata.keys()) - chromadb_files
    print(f"Papers to sync: {len(missing_files)}")
    print()

    if not missing_files:
        print("✓ All papers are already in ChromaDB!")
        return

    # Add missing papers to ChromaDB
    added = 0
    failed = 0

    for filename in sorted(missing_files):
        paper = all_metadata[filename]

        try:
            doc_id = f"{filename}_metadata"

            # Delete if exists (shouldn't, but just in case)
            try:
                collection.delete(ids=[doc_id])
            except:
                pass

            # Prepare metadata
            authors = paper.get('authors', [])
            if isinstance(authors, list):
                authors_str = '; '.join(authors)
            else:
                authors_str = str(authors)

            # Add to ChromaDB with all required fields
            collection.add(
                documents=[f"Metadata: {paper.get('title', '')}. DOI: {paper.get('doi', '')}"],
                metadatas=[{
                    'filename': filename,
                    'page_num': 0,
                    'paper_type': paper.get('paper_type', 'experimental'),
                    'application': paper.get('application', 'general'),
                    'chemistries': ','.join(paper.get('chemistries', [])) if isinstance(paper.get('chemistries'), list) else '',
                    'topics': ','.join(paper.get('topics', [])) if isinstance(paper.get('topics'), list) else '',
                    'section_name': 'metadata',
                    'abstract': paper.get('abstract', ''),
                    'author_keywords': ';'.join(paper.get('author_keywords', [])) if isinstance(paper.get('author_keywords'), list) else '',
                    'title': paper.get('title', ''),
                    'authors': authors_str,
                    'year': str(paper.get('year', '')),
                    'journal': paper.get('journal', ''),
                    'doi': paper.get('doi', '')
                }],
                ids=[doc_id]
            )

            added += 1
            if added % 10 == 0:
                print(f"Added {added}/{len(missing_files)}...")

        except Exception as e:
            print(f"Failed to add {filename}: {str(e)}")
            failed += 1

    # Clear cache to force reload
    DatabaseClient.clear_cache()

    print()
    print("=" * 80)
    print(f"✓ Sync complete!")
    print(f"  Added: {added}")
    print(f"  Failed: {failed}")
    print(f"  Total: {len(missing_files)}")
    print("=" * 80)

    # Verify
    collection = DatabaseClient.get_collection()
    all_results = collection.get(include=["metadatas"])
    chromadb_files_after = set(m.get('filename', '') for m in all_results['metadatas'] if m.get('filename'))
    print(f"\nVerification:")
    print(f"  Papers in ChromaDB after sync: {len(chromadb_files_after)}")
    print(f"  Expected: {len(all_metadata)}")

    if len(chromadb_files_after) == len(all_metadata):
        print("\n✓ All papers are now in sync!")
    else:
        print(f"\n⚠ Still missing {len(all_metadata) - len(chromadb_files_after)} papers")

if __name__ == "__main__":
    sync_metadata_to_chromadb()
