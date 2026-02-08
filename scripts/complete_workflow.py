"""
Complete workflow: Wait for pipeline → Process → Enrich → Sync
Runs unattended with progress reporting.
"""
import subprocess
import time
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PIPELINE_STATE_FILE = BASE_DIR / "data" / "pipeline_state.json"
METADATA_FILE = BASE_DIR / "data" / "metadata.json"

def check_pipeline_complete():
    """Check if pipeline has completed all stages"""
    if not PIPELINE_STATE_FILE.exists():
        return False

    with open(PIPELINE_STATE_FILE, 'r') as f:
        state = json.load(f)

    parsed = state.get('parsed', [])
    embedded = state.get('embedded', [])

    return len(parsed) > 0 and len(embedded) > 0

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

def run_script(script_name, description):
    """Run a script and print its output"""
    print("\n" + "=" * 70)
    print(f"{description}")
    print("=" * 70)

    result = subprocess.run(
        ["python", f"scripts/{script_name}"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.stderr:
        print("Stderr:", result.stderr)

    return result.returncode == 0

def main():
    print("=" * 70)
    print("COMPLETE ENRICHMENT WORKFLOW")
    print("=" * 70)
    print("This will:")
    print("  1. Wait for current pipeline to complete")
    print("  2. Categorize papers by status")
    print("  3. Sync status to ChromaDB")
    print("  4. Enrich all incomplete/metadata-only papers")
    print("  5. Re-categorize and sync")
    print("  6. Report final results")
    print()

    # Step 1: Wait for pipeline
    print("STEP 1: Waiting for pipeline to complete...")
    print("=" * 70)
    wait_time = 0
    while True:
        if check_pipeline_complete():
            print(f"\nPipeline complete after {wait_time} seconds")
            break

        if wait_time % 60 == 0 and wait_time > 0:
            print(f"  Still waiting... ({wait_time // 60} minutes elapsed)")

        time.sleep(10)
        wait_time += 10

    # Additional wait to ensure pipeline fully finished
    print("Waiting 30 seconds to ensure pipeline has fully completed...")
    time.sleep(30)

    print_stats("STATUS AFTER PIPELINE")

    # Step 2: Mark incomplete metadata
    run_script("mark_incomplete_metadata.py", "STEP 2: Categorizing papers by metadata completeness")
    print_stats("STATUS AFTER CATEGORIZATION")

    # Step 3: Sync to ChromaDB
    run_script("sync_status_to_chromadb.py", "STEP 3: Syncing status to ChromaDB")

    # Step 4: Enrich all papers
    run_script("enrich_all_papers.py", "STEP 4: Enriching all incomplete/metadata-only papers")
    print_stats("STATUS AFTER ENRICHMENT")

    # Step 5: Re-categorize
    run_script("mark_incomplete_metadata.py", "STEP 5: Re-categorizing papers after enrichment")
    print_stats("STATUS AFTER RE-CATEGORIZATION")

    # Step 6: Re-sync to ChromaDB
    run_script("sync_status_to_chromadb.py", "STEP 6: Final sync to ChromaDB")

    # Final summary
    print("\n" + "=" * 70)
    print("WORKFLOW COMPLETE!")
    print("=" * 70)
    print_stats("FINAL STATUS")
    print("\nNext step: Restart the Streamlit UI to see updated stats")

if __name__ == "__main__":
    main()
