"""
Full resync of ALL papers from metadata.json to ChromaDB
Updates metadata for existing papers and adds missing ones
"""
import json
from pathlib import Path
from lib.rag import DatabaseClient

def full_resync():
    """Update ALL papers in ChromaDB to match metadata.json"""

    # Load metadata.json
    metadata_file = Path("data/metadata.json")
    with open(metadata_file, 'r', encoding='utf-8') as f:
        all_metadata = json.load(f)

    print(f"Papers in metadata.json: {len(all_metadata)}")
    print()

    # Get ChromaDB collection
    DatabaseClient.clear_cache()
    collection = DatabaseClient.get_collection()

    updated = 0
    added = 0
    failed = 0

    for filename, paper in all_metadata.items():
        try:
            doc_id = f"{filename}_metadata"

            # Prepare metadata
            authors = paper.get('authors', [])
            if isinstance(authors, list):
                authors_str = '; '.join(authors)
            else:
                authors_str = str(authors)

            # Delete if exists
            try:
                collection.delete(ids=[doc_id])
                updated += 1
            except:
                added += 1

            # Add with complete metadata
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

            if (updated + added) % 20 == 0:
                print(f"Processed {updated + added}/{len(all_metadata)}...")

        except Exception as e:
            print(f"Failed to sync {filename}: {str(e)}")
            failed += 1

    # Clear cache
    DatabaseClient.clear_cache()

    print()
    print("="*80)
    print("Resync complete!")
    print(f"  Updated: {updated}")
    print(f"  Added: {added}")
    print(f"  Failed: {failed}")
    print(f"  Total: {len(all_metadata)}")
    print("="*80)

    # Verify
    print("\nVerifying...")
    from lib import rag
    from pathlib import Path as P

    papers = rag.get_paper_library()

    complete = 0
    metadata_only = 0
    incomplete = 0

    for paper in papers:
        has_title = bool(paper.get('title', '').strip())
        has_authors = bool(paper.get('authors') and paper.get('authors') != [])
        has_year = bool(paper.get('year', '').strip())
        has_journal = bool(paper.get('journal', '').strip())
        metadata_complete = has_title and has_authors and has_year and has_journal

        pdf_path = P('papers') / paper.get('filename', '')
        has_pdf = pdf_path.exists()

        if metadata_complete and has_pdf:
            complete += 1
        elif metadata_complete and not has_pdf:
            metadata_only += 1
        else:
            incomplete += 1

    print(f"\nChromaDB stats after resync:")
    print(f"  Complete: {complete}")
    print(f"  Metadata Only: {metadata_only}")
    print(f"  Incomplete: {incomplete}")
    print(f"  Total: {len(papers)}")

if __name__ == "__main__":
    full_resync()
