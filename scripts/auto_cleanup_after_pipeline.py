"""
Automatic cleanup after pipeline completes
Waits for pipeline, then runs cleanup scripts with stats reporting
"""

import subprocess
import time
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "metadata.json"
PIPELINE_STATE_FILE = BASE_DIR / "data" / "pipeline_state.json"

def get_stats():
    """Get current paper statistics"""
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    status_counts = {}
    for filename, paper in metadata.items():
        status = paper.get('pdf_status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1

    return status_counts, len(metadata)

def print_stats(label):
    """Print current statistics"""
    print("\n" + "=" * 70)
    print(f"{label}")
    print("=" * 70)

    status_counts, total = get_stats()

    print(f"Total papers: {total}")
    print(f"\nBreakdown by status:")
    for status in sorted(status_counts.keys()):
        count = status_counts[status]
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {status}: {count} ({pct:.1f}%)")

    # Count PDFs on disk
    papers_dir = BASE_DIR / "papers"
    valid_pdfs = len(list(papers_dir.glob("*.pdf")))
    invalid_dir = BASE_DIR / "papers_invalid"
    invalid_pdfs = len(list(invalid_dir.glob("*.pdf")))

    print(f"\nPDFs on disk:")
    print(f"  Valid: {valid_pdfs}")
    print(f"  Invalid: {invalid_pdfs}")

def check_pipeline_complete():
    """Check if pipeline has completed all stages"""
    if not PIPELINE_STATE_FILE.exists():
        return False

    with open(PIPELINE_STATE_FILE, 'r') as f:
        state = json.load(f)

    # Check if all stages have entries
    parsed = state.get('parsed', [])
    chunked = state.get('chunked', [])
    metadata_extracted = state.get('metadata', [])
    embedded = state.get('embedded', [])

    # Pipeline is complete if we have papers in all stages
    # and the counts are stable
    return len(parsed) > 0 and len(embedded) > 0

def main():
    print("Waiting for pipeline to complete...")
    print("(This script will wait until ingest_pipeline.py finishes all stages)")

    # Wait for pipeline to complete
    # Check every 2 minutes
    wait_time = 0
    while True:
        if check_pipeline_complete():
            print(f"\nPipeline appears complete after {wait_time} minutes")
            break

        if wait_time % 10 == 0:  # Print every 10 minutes
            print(f"  Still waiting... ({wait_time} minutes elapsed)")

        time.sleep(120)  # Wait 2 minutes
        wait_time += 2

    # Additional wait to ensure pipeline fully finished
    print("Waiting 30 seconds to ensure pipeline has fully completed...")
    time.sleep(30)

    # Show initial stats
    print_stats("INITIAL STATE (after pipeline)")

    # Step 1: Run ChromaDB cleanup
    print("\n" + "=" * 70)
    print("STEP 1: Cleaning up invalid PDFs from ChromaDB")
    print("=" * 70)

    result = subprocess.run(
        ["python", "scripts/cleanup_invalid_chromadb.py"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        input="yes\n"  # Auto-confirm
    )

    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)

    print_stats("AFTER CHROMADB CLEANUP")

    # Step 2: Run metadata categorization
    print("\n" + "=" * 70)
    print("STEP 2: Categorizing papers by metadata completeness")
    print("=" * 70)

    result = subprocess.run(
        ["python", "scripts/mark_incomplete_metadata.py"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)

    print_stats("FINAL STATE (after metadata categorization)")

    # Final summary
    print("\n" + "=" * 70)
    print("CLEANUP COMPLETE!")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Restart the Streamlit UI to see updated Library Stats")
    print("2. The UI will now show papers categorized as:")
    print("   - complete: verified metadata + PDF + fully processed")
    print("   - incomplete: incomplete/unverified metadata")
    print("   - processing_pending: verified metadata + PDF but not processed")
    print("   - metadata_only: verified metadata but no PDF")
    print("\nIf the numbers look wrong, check the logs above for issues.")

if __name__ == "__main__":
    main()
