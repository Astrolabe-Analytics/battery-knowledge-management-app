"""
Mark papers with incomplete metadata (CrossRef failures) as incomplete
Papers without verified CrossRef data should not be marked as "complete"
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"
PIPELINE_LOG = BASE_DIR / "data" / "pipeline.log"

def find_crossref_failures_from_logs() -> set:
    """Parse pipeline logs to find papers where CrossRef failed"""
    crossref_failures = set()

    # Try to find log file or task output
    possible_logs = [
        BASE_DIR / "data" / "pipeline.log",
        Path(r"C:\Users\rcmas\AppData\Local\Temp\claude\C--Users-rcmas-astrolabe-paper-db\tasks\b3dde0f.output")
    ]

    log_content = ""
    for log_path in possible_logs:
        if log_path.exists():
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    log_content = f.read()
                break
            except:
                continue

    if not log_content:
        print("Warning: Could not find pipeline log file")
        return crossref_failures

    # Pattern: "Processing <filename>" followed by "CrossRef query failed"
    lines = log_content.split('\n')
    current_paper = None

    for line in lines:
        # Look for "Processing <filename>"
        if "Processing" in line and ".pdf" in line:
            match = re.search(r'Processing (.+?\.pdf)', line)
            if match:
                current_paper = match.group(1)

        # Look for CrossRef failure for current paper
        if current_paper and "CrossRef query failed" in line:
            crossref_failures.add(current_paper)
            current_paper = None  # Reset

    return crossref_failures

def check_metadata_completeness(paper_metadata: dict) -> tuple[bool, list]:
    """
    Check if paper has complete metadata.
    Returns (is_complete, missing_fields)
    """
    missing_fields = []

    # Critical fields that should come from CrossRef
    if not paper_metadata.get('journal'):
        missing_fields.append('journal')

    if not paper_metadata.get('title'):
        missing_fields.append('title')

    if not paper_metadata.get('authors') or len(paper_metadata.get('authors', [])) == 0:
        missing_fields.append('authors')

    if not paper_metadata.get('year'):
        missing_fields.append('year')

    # If missing any critical field, mark as incomplete
    is_complete = len(missing_fields) == 0

    return is_complete, missing_fields

def main():
    print("Checking metadata completeness and pdf_status consistency...")
    print("=" * 60)

    # Load metadata
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    print(f"Total papers in metadata: {len(metadata)}")

    # Get actual PDFs on disk
    papers_dir = BASE_DIR / "papers"
    valid_pdfs = {f.name for f in papers_dir.glob("*.pdf")}
    print(f"Valid PDFs on disk: {len(valid_pdfs)}")

    # Find CrossRef failures from logs
    crossref_failures = find_crossref_failures_from_logs()
    print(f"Papers with CrossRef failures (from logs): {len(crossref_failures)}")

    # Check each paper's metadata completeness
    incomplete_papers = []
    incomplete_reasons = {}

    for filename, paper_data in metadata.items():
        is_complete, missing_fields = check_metadata_completeness(paper_data)

        if not is_complete:
            incomplete_papers.append(filename)
            incomplete_reasons[filename] = missing_fields

    # Combine all papers with incomplete metadata
    all_incomplete_metadata = set(incomplete_papers) | crossref_failures

    print(f"\nPapers with incomplete metadata:")
    print(f"  Missing critical fields: {len(incomplete_papers)}")
    print(f"  CrossRef query failures: {len(crossref_failures)}")
    print(f"  Total with incomplete metadata: {len(all_incomplete_metadata)}")

    if all_incomplete_metadata:
        print("\nSample papers with incomplete metadata (first 10):")
        for filename in list(all_incomplete_metadata)[:10]:
            reason = incomplete_reasons.get(filename, ['CrossRef failure'])
            print(f"  {filename}: {', '.join(reason)}")

    # Check pipeline state to see which papers are fully processed
    pipeline_state_file = BASE_DIR / "data" / "pipeline_state.json"
    fully_processed = set()

    if pipeline_state_file.exists():
        with open(pipeline_state_file, 'r') as f:
            pipeline_state = json.load(f)

        # Papers must be in ALL stages to be considered fully processed
        parsed = set(pipeline_state.get('parsed', []))
        chunked = set(pipeline_state.get('chunked', []))
        embedded = set(pipeline_state.get('embedded', []))

        # Only papers that went through all stages
        fully_processed = parsed & chunked & embedded
        print(f"\nFully processed papers (parsed + chunked + embedded): {len(fully_processed)}")

    # Assign pdf_status based on rules
    print(f"\nAssigning paper statuses...")

    summarized_count = 0
    complete_count = 0
    incomplete_count = 0
    metadata_only_count = 0
    processing_pending_count = 0

    for filename in metadata:
        has_pdf = filename in valid_pdfs
        has_complete_metadata = filename not in all_incomplete_metadata
        is_fully_processed = filename in fully_processed
        has_ai_summary = bool(metadata[filename].get('ai_summary', '').strip())

        # Rule 1: Incomplete metadata → "incomplete" (regardless of PDF)
        if not has_complete_metadata:
            metadata[filename]['pdf_status'] = 'incomplete'
            metadata[filename]['metadata_incomplete'] = True
            metadata[filename]['crossref_verified'] = False
            incomplete_count += 1

        # Rule 2: Complete metadata + NO PDF → "metadata_only"
        elif has_complete_metadata and not has_pdf:
            metadata[filename]['pdf_status'] = 'metadata_only'
            metadata[filename]['metadata_incomplete'] = False
            metadata[filename]['crossref_verified'] = True
            metadata_only_count += 1

        # Rule 3a: Complete metadata + PDF + fully processed + AI summary → "summarized"
        elif has_complete_metadata and has_pdf and is_fully_processed and has_ai_summary:
            metadata[filename]['pdf_status'] = 'summarized'
            metadata[filename]['metadata_incomplete'] = False
            metadata[filename]['crossref_verified'] = True
            summarized_count += 1

        # Rule 3b: Complete metadata + PDF + fully processed (no AI summary) → "complete"
        elif has_complete_metadata and has_pdf and is_fully_processed:
            metadata[filename]['pdf_status'] = 'complete'
            metadata[filename]['metadata_incomplete'] = False
            metadata[filename]['crossref_verified'] = True
            complete_count += 1

        # Rule 4: Complete metadata + has PDF + NOT fully processed → "processing_pending"
        elif has_complete_metadata and has_pdf and not is_fully_processed:
            metadata[filename]['pdf_status'] = 'processing_pending'
            metadata[filename]['metadata_incomplete'] = False
            metadata[filename]['crossref_verified'] = True
            metadata[filename]['needs_processing'] = True
            processing_pending_count += 1

    print(f"  Summarized: {summarized_count}")
    print(f"  Complete: {complete_count}")
    print(f"  Incomplete: {incomplete_count}")
    print(f"  Processing pending: {processing_pending_count}")
    print(f"  Metadata-only: {metadata_only_count}")

    # Save updated metadata
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"Updated metadata.json with completeness flags")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Summarized: {summarized_count} (complete metadata + PDF + fully processed + AI summary)")
    print(f"Complete: {complete_count} (complete metadata + PDF + fully processed)")
    print(f"Incomplete: {incomplete_count} (incomplete/unverified metadata)")
    print(f"Processing pending: {processing_pending_count} (complete metadata + PDF, needs processing)")
    print(f"Metadata-only: {metadata_only_count} (complete metadata, no PDF)")
    print(f"\nTotal papers: {len(metadata)}")
    print(f"\nStatus categories:")
    print(f"  - 'complete': Ready for full-text search")
    print(f"  - 'incomplete': Metadata issues (CrossRef failed or missing fields)")
    print(f"  - 'processing_pending': Has PDF + verified metadata, needs parse/chunk/embed")
    print(f"  - 'metadata_only': Bibliographic record only (no PDF)")
    print(f"\nMetadata fields:")
    print(f"  - 'pdf_status': complete | incomplete | processing_pending | metadata_only")
    print(f"  - 'metadata_incomplete': true if metadata missing/unverified")
    print(f"  - 'crossref_verified': true if CrossRef data retrieved")
    print(f"  - 'needs_processing': true if has PDF but not fully processed")

if __name__ == "__main__":
    main()
